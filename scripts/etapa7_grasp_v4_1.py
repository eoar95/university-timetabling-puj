"""
===============================================================
SCHEDULING ACADÉMICO — JAVERIANA INGENIERÍA
Etapa 7: Metaheurística GRASP — v4.1
===============================================================
Cambios respecto a v4.0:
  - Se agrega S5 — Continuidad intra-asignatura.
    Penaliza huecos internos entre bloques de la misma sección
    dentro del mismo día.
    Fórmula: C_cont = ∑_{s,d} max(0, span_{s,d} − bloques_{s,d})
    donde span_{s,d} = p_ultimo_{s,d} − p_primero_{s,d} + 1.
    Peso: W_CONT = 5.
    Implementación construcción: delta_continuidad(s,d,p) en costo_slot.
    Implementación búsqueda local: delta S5 en delta_move, con
    gaps_seccion_sin / gaps_seccion_con para cómputo O(1).

  - Se agrega S6 — Estabilidad de salón intra-asignatura.
    Penaliza usar más de un salón para una misma sección dentro
    del mismo día.
    Fórmula: C_salon = ∑_{s,d} max(0, n_salones_{s,d} − 1)
    Peso: W_SALON = 6.
    Implementación construcción: c_salon en costo_slot; section_day_rooms
    registra salones por (sección, día).
    Implementación búsqueda local: delta S6 en delta_move; recomputa
    raw_salon(slots, d) sobre días afectados {d_old, d_new}.

Pesos finales v4.1:
    W_DESP=1, W_HUECOS=2, W_EXCESO=3, W_CONC=4, W_CONT=5, W_SALON=6

Uso:
    python etapa7_grasp_v4_1.py [piloto|mediana|completa] [alpha] [n_iter]

    alpha:  0.1 · 0.2 · 0.3  (default 0.3)
    n_iter: default piloto=100, mediana/completa=50

Salidas (./resultados/):
    grasp_v41_<inst>_a<alpha>_resumen.csv
    grasp_v41_<inst>_a<alpha>_horario.csv
    grasp_v41_<inst>_a<alpha>_convergencia.csv
===============================================================
"""

import sys, os, time, random
import pandas as pd
from collections import defaultdict

# ══════════════════════════════════════════════════════════════
# PARÁMETROS GLOBALES (v4.1)
# ══════════════════════════════════════════════════════════════
DIAS      = list(range(5))
PERIODOS  = list(range(10))
N_MAX_DIA = 6
UMBRAL_CAP= 10
W_DESP=1; W_HUECOS=2; W_EXCESO=3; W_CONC=4; W_CONT=5; W_SALON=6
MAX_PASADAS_LOCAL = 3

NOMBRE_DIA   = {0:'Lunes',1:'Martes',2:'Miércoles',3:'Jueves',4:'Viernes'}
HORA_PERIODO = {i:f"{7+i}:00-{8+i}:00" for i in range(10)}
DATA_DIR="C:\\Users\\eoar9\\Documents\\Visual Studio\\01 Universidad\\Optimizacion\\Proyecto Final"
OUT_DIR='resultados'

INSTANCIAS_CONFIG = {
    'piloto':   {'carreras_fijas':['Bioingeniería'],'n_carreras':None,
                 'n_iter_default':100,'time_limit':120},
    'mediana':  {'carreras_fijas':None,'n_carreras':4,
                 'n_iter_default':50,'time_limit':300},
    'completa': {'carreras_fijas':None,'n_carreras':None,
                 'n_iter_default':50,'time_limit':600},
}
os.makedirs(OUT_DIR, exist_ok=True)


# ══════════════════════════════════════════════════════════════
# 1. CARGA Y PRECÓMPUTO
# ══════════════════════════════════════════════════════════════
def cargar_datos(nombre):
    cfg = INSTANCIAS_CONFIG[nombre]
    df_secc   = pd.read_csv(f'{DATA_DIR}/tabla_secciones.csv')
    df_sal    = pd.read_csv(f'{DATA_DIR}/tabla_salones.csv')
    df_compat = pd.read_csv(f'{DATA_DIR}/tabla_compatibilidad.csv')

    todas = sorted(df_secc['carrera'].unique())
    if cfg['carreras_fijas']:    carreras = cfg['carreras_fijas']
    elif cfg['n_carreras']:      carreras = todas[:cfg['n_carreras']]
    else:                        carreras = todas

    df_secc = df_secc[df_secc['carrera'].isin(carreras)].reset_index(drop=True)
    df_compat_secc = (
        df_secc[['id_seccion','id_asignatura','estudiantes_estimados']]
        .merge(df_compat[['id_asignatura','id_salon','capacidad_salon']],
               on='id_asignatura', how='inner')
    )
    print(f"\n  '{nombre}': {len(carreras)} carreras | "
          f"{len(df_secc)} secciones | {df_secc['bloques_semanales'].sum()} bloques")
    return df_secc, df_sal, df_compat_secc


def precomputar(df_secc, df_sal, df_compat_secc):
    secc_info = df_secc.set_index('id_seccion').to_dict('index')
    sal_cap   = df_sal.set_index('id_salon')['capacidad'].to_dict()

    sal_por_secc = defaultdict(list)
    for _, row in df_compat_secc.iterrows():
        sal_por_secc[row['id_seccion']].append(row['id_salon'])
    for s in sal_por_secc:
        est = secc_info[s]['estudiantes_estimados']
        sal_por_secc[s].sort(key=lambda r: sal_cap.get(r,9999)-est)

    grupos = defaultdict(list)
    grupo_de_secc = {}
    for _, row in df_secc.iterrows():
        g = (row['carrera'], row['semestre'], row['grupo'])
        grupos[g].append(row['id_seccion'])
        grupo_de_secc[row['id_seccion']] = g

    return secc_info, sal_cap, sal_por_secc, grupos, grupo_de_secc


# ══════════════════════════════════════════════════════════════
# 2. ESTADO DEL HORARIO
# ══════════════════════════════════════════════════════════════
class EstadoHorario:
    def __init__(self):
        self.room_slot         = {}
        self.group_slot        = defaultdict(lambda: defaultdict(lambda: defaultdict(bool)))
        self.section_slots     = defaultdict(list)
        self.section_days      = defaultdict(set)   # s → {días usados}
        self.section_day_rooms = defaultdict(lambda: defaultdict(set))  # s → d → {salones usados}
        self.group_day_periods = defaultdict(lambda: defaultdict(list))

    def libre_salon(self, r, d, p): return (r,d,p) not in self.room_slot
    def libre_grupo(self, g, d, p): return not self.group_slot[g][d][p]

    def asignar(self, s, r, d, p, g):
        self.room_slot[(r,d,p)] = s
        self.group_slot[g][d][p] = True
        self.section_slots[s].append((r,d,p))
        self.section_days[s].add(d)
        self.section_day_rooms[s][d].add(r)
        self.group_day_periods[g][d].append(p)

    def liberar(self, s, r, d, p, g):
        del self.room_slot[(r,d,p)]
        self.group_slot[g][d][p] = False
        self.section_slots[s].remove((r,d,p))
        self.group_day_periods[g][d].remove(p)
        # Recalcular días si ya no hay bloques de s ese día
        if not self.group_day_periods[g][d] or \
           not any(d2==d for r2,d2,p2 in self.section_slots[s]):
            self.section_days[s].discard(d)
        if not any(r2==r and d2==d for r2,d2,p2 in self.section_slots[s]):
            self.section_day_rooms[s][d].discard(r)

    def gaps(self, g, d):
        ps = self.group_day_periods[g][d]
        return (max(ps)-min(ps)+1-len(ps)) if len(ps)>=2 else 0

    def gaps_con(self, g, d, p_add):
        ps = self.group_day_periods[g][d]
        if not ps: return 0
        nm=min(min(ps),p_add); nx=max(max(ps),p_add)
        return (nx-nm+1)-(len(ps)+1)

    def gaps_sin(self, g, d, p_rem):
        ps = [p for p in self.group_day_periods[g][d] if p!=p_rem]
        return (max(ps)-min(ps)+1-len(ps)) if len(ps)>=2 else 0

    def periodos_seccion(self, s, d):
        return [p for r2,d2,p in self.section_slots[s] if d2 == d]

    def gaps_seccion(self, s, d):
        ps = self.periodos_seccion(s, d)
        return (max(ps)-min(ps)+1-len(ps)) if len(ps)>=2 else 0

    def gaps_seccion_con(self, s, d, p_add):
        ps = self.periodos_seccion(s, d)
        if not ps:
            return 0
        nm = min(min(ps), p_add); nx = max(max(ps), p_add)
        return (nx-nm+1) - (len(ps)+1)

    def gaps_seccion_sin(self, s, d, p_rem):
        ps = [p for p in self.periodos_seccion(s, d) if p != p_rem]
        return (max(ps)-min(ps)+1-len(ps)) if len(ps)>=2 else 0

    def delta_continuidad(self, s, d, p):
        ps = self.periodos_seccion(s, d)
        if not ps:
            return 0
        return self.gaps_seccion_con(s, d, p) - self.gaps_seccion(s, d)

    def clonar(self):
        n = EstadoHorario()
        n.room_slot = dict(self.room_slot)
        n.group_slot = defaultdict(lambda: defaultdict(lambda: defaultdict(bool)))
        for g in self.group_slot:
            for d in self.group_slot[g]:
                for p,v in self.group_slot[g][d].items():
                    n.group_slot[g][d][p] = v
        n.section_slots  = defaultdict(list,  {s:list(v)  for s,v in self.section_slots.items()})
        n.section_days   = defaultdict(set,   {s:set(v)   for s,v in self.section_days.items()})
        n.section_day_rooms = defaultdict(lambda: defaultdict(set),
                               {s: defaultdict(set,{d:set(rs) for d,rs in dias.items()})
                                for s,dias in self.section_day_rooms.items()})
        n.group_day_periods = defaultdict(lambda: defaultdict(list),
                               {g: defaultdict(list,{d:list(ps) for d,ps in dias.items()})
                                for g,dias in self.group_day_periods.items()})
        return n


# ══════════════════════════════════════════════════════════════
# 3. COSTOS
# ══════════════════════════════════════════════════════════════
def costo_slot(s, r, d, p, g, estado, secc_info, sal_cap):
    """Costo greedy local — v4.1: incluye S5 continuidad y S6 estabilidad de salón."""
    est = secc_info[s]['estudiantes_estimados']
    c_desp  = max(0, sal_cap[r]-est-UMBRAL_CAP)
    ps = estado.group_day_periods[g][d]
    if not ps:
        delta_gap = 0
    else:
        nm=min(min(ps),p); nx=max(max(ps),p)
        delta_gap = (nx-nm+1)-(len(ps)+1) - ((max(ps)-min(ps)+1-len(ps)) if len(ps)>=2 else 0)
    c_huecos = delta_gap
    c_exceso = max(0, len(ps)+1-N_MAX_DIA)
    # S4: penalizar día nuevo solo cuando la sección ya tiene ≥ 1 día asignado
    c_conc = 1 if estado.section_days[s] and d not in estado.section_days[s] else 0
    # S5: huecos internos de la misma sección dentro del día
    c_cont = estado.delta_continuidad(s, d, p)
    # S6 v4.1: penalizar un salón nuevo para la sección dentro del mismo día
    c_salon = 1 if estado.section_day_rooms[s][d] and r not in estado.section_day_rooms[s][d] else 0
    return (W_DESP*c_desp + W_HUECOS*c_huecos + W_EXCESO*c_exceso +
            W_CONC*c_conc + W_CONT*c_cont + W_SALON*c_salon)


def fobj_total(estado, secc_info, sal_cap):
    """f_obj v4.1: incluye S5 continuidad intra-asignatura."""
    c_desp = sum(max(0,sal_cap[r]-secc_info[s]['estudiantes_estimados']-UMBRAL_CAP)
                 for s,slots in estado.section_slots.items() for r,d,p in slots)
    c_huecos = sum(estado.gaps(g,d)
                   for g,dias in estado.group_day_periods.items() for d in dias)
    c_exceso = sum(max(0,len(ps)-N_MAX_DIA)
                   for g,dias in estado.group_day_periods.items()
                   for d,ps in dias.items())
    # S4: concentración diaria
    c_conc_raw = sum(max(0,len(dias)-1) for dias in estado.section_days.values())
    # S5 v4.1: continuidad intra-asignatura
    c_cont_raw = sum(estado.gaps_seccion(s, d)
                     for s in estado.section_slots for d in DIAS)
    c_salon_raw = sum(max(0, len(rooms)-1)
                      for dias in estado.section_day_rooms.values()
                      for rooms in dias.values())
    return (W_DESP*c_desp + W_HUECOS*c_huecos + W_EXCESO*c_exceso +
            W_CONC*c_conc_raw + W_CONT*c_cont_raw + W_SALON*c_salon_raw)


def delta_move(s, r_old, d_old, p_old, r_new, d_new, p_new,
               g, estado, secc_info, sal_cap):
    """Cambio en f_obj al mover bloque — O(1).
    S4: el delta de max(0, n_días_s−1) es algebraicamente
    idéntico al delta de n_días_s cuando n_días_s ≥ 1,
    que es siempre el caso en la búsqueda local (sección ya asignada).
    Por tanto delta_move no requiere cambios respecto a v2.0."""
    est = secc_info[s]['estudiantes_estimados']

    # ΔS1
    ds1 = max(0,sal_cap[r_new]-est-UMBRAL_CAP) - max(0,sal_cap[r_old]-est-UMBRAL_CAP)

    # ΔS2 (huecos del grupo)
    if d_new == d_old:
        ps = estado.group_day_periods[g][d_old]
        gaps_antes = estado.gaps(g,d_old)
        ps_tmp = [p for p in ps if p!=p_old]+[p_new]
        gaps_desp = (max(ps_tmp)-min(ps_tmp)+1-len(ps_tmp)) if len(ps_tmp)>=2 else 0
        ds2 = gaps_desp - gaps_antes
    else:
        ds2 = (estado.gaps_sin(g,d_old,p_old) - estado.gaps(g,d_old) +
               estado.gaps_con(g,d_new,p_new) - estado.gaps(g,d_new))

    # ΔS3 (exceso)
    if d_new == d_old:
        ds3 = 0
    else:
        n_old = len(estado.group_day_periods[g][d_old])
        n_new = len(estado.group_day_periods[g][d_new])
        ds3 = (max(0,n_old-1-N_MAX_DIA)-max(0,n_old-N_MAX_DIA) +
               max(0,n_new+1-N_MAX_DIA)-max(0,n_new-N_MAX_DIA))

    # ΔS4: cambio en días usados por sección s
    if d_new == d_old:
        ds4 = 0
    else:
        sigue_d_old = any(d2==d_old for r2,d2,p2 in estado.section_slots[s]
                          if not(r2==r_old and d2==d_old and p2==p_old))
        ya_usa_d_new = d_new in estado.section_days[s]
        dias_delta = (0 if sigue_d_old else -1) + (0 if ya_usa_d_new else 1)
        ds4 = W_CONC * dias_delta

    # ΔS5 v4.1: cambio en huecos internos de la misma sección
    if d_new == d_old:
        gaps_antes = estado.gaps_seccion(s, d_old)
        ps_tmp = [p for r2,d2,p in estado.section_slots[s]
                  if d2 == d_old and not (r2==r_old and p==p_old)] + [p_new]
        gaps_desp = (max(ps_tmp)-min(ps_tmp)+1-len(ps_tmp)) if len(ps_tmp)>=2 else 0
        ds5 = gaps_desp - gaps_antes
    else:
        ds5 = (estado.gaps_seccion_sin(s,d_old,p_old) - estado.gaps_seccion(s,d_old) +
               estado.gaps_seccion_con(s,d_new,p_new) - estado.gaps_seccion(s,d_new))

    # ΔS6 v4.1: cambio en salones extra por sección/día
    slots_actuales = list(estado.section_slots[s])
    slots_nuevos = [(r2,d2,p2) for r2,d2,p2 in slots_actuales
                    if not (r2==r_old and d2==d_old and p2==p_old)] + [(r_new,d_new,p_new)]

    def raw_salon(slots, d):
        return max(0, len({r2 for r2,d2,p2 in slots if d2 == d}) - 1)

    dias_afectados = {d_old, d_new}
    ds6 = sum(raw_salon(slots_nuevos, d) - raw_salon(slots_actuales, d)
              for d in dias_afectados)

    return (W_DESP*ds1 + W_HUECOS*ds2 + W_EXCESO*ds3 + ds4 +
            W_CONT*ds5 + W_SALON*ds6)


# ══════════════════════════════════════════════════════════════
# 4. FASE 1: CONSTRUCCIÓN GRASP
# ══════════════════════════════════════════════════════════════
def ordenar_secciones(df_secc, sal_por_secc, secc_info):
    secs = list(df_secc['id_seccion'])
    secs.sort(key=lambda s: (
        -secc_info[s]['bloques_semanales']/max(len(sal_por_secc[s]),1),
        -secc_info[s]['bloques_semanales'], s))
    return secs


def construccion(df_secc, sal_por_secc, grupo_de_secc,
                 secc_info, sal_cap, alpha, rng):
    estado    = EstadoHorario()
    secciones = ordenar_secciones(df_secc, sal_por_secc, secc_info)

    for s in secciones:
        b_s = secc_info[s]['bloques_semanales']
        g   = grupo_de_secc[s]
        sal = sal_por_secc[s]

        for _ in range(b_s):
            # Días ya usados por s primero (S4=0), luego días nuevos
            dias_usados = sorted(estado.section_days[s],
                                 key=lambda d:(len(estado.group_day_periods[g][d]),d))
            dias_nuevos = sorted([d for d in DIAS if d not in estado.section_days[s]],
                                 key=lambda d:(len(estado.group_day_periods[g][d]),d))
            dias_ord = dias_usados + dias_nuevos

            candidatos = []
            for d in dias_ord:
                for p in PERIODOS:
                    if estado.group_slot[g][d][p]: continue
                    for r in sal:
                        if (r,d,p) in estado.room_slot: continue
                        c = costo_slot(s,r,d,p,g,estado,secc_info,sal_cap)
                        candidatos.append((c,d,p,r))

            if not candidatos: continue

            c_min = candidatos[0][0]
            c_max = max(x[0] for x in candidatos)
            umbral = c_min + alpha*(c_max-c_min)
            rcl = [x for x in candidatos if x[0]<=umbral]
            _,d_a,p_a,r_a = rng.choice(rcl)
            estado.asignar(s,r_a,d_a,p_a,g)

    return estado


# ══════════════════════════════════════════════════════════════
# 5. FASE 2: BÚSQUEDA LOCAL (evaluación delta O(1))
# ══════════════════════════════════════════════════════════════
def busqueda_local(estado, sal_por_secc, grupo_de_secc,
                   secc_info, sal_cap):
    for _ in range(MAX_PASADAS_LOCAL):
        mejoro = False
        bloques = [(s,r,d,p) for s,slots in estado.section_slots.items()
                   for r,d,p in list(slots)]
        random.shuffle(bloques)

        for s,r_old,d_old,p_old in bloques:
            g   = grupo_de_secc[s]
            sal = sal_por_secc[s]
            mejor_delta = 0.0
            mejor_slot  = None

            for r_new in sal:
                for d_new in DIAS:
                    for p_new in PERIODOS:
                        if r_new==r_old and d_new==d_old and p_new==p_old: continue
                        if not estado.libre_salon(r_new,d_new,p_new): continue
                        if not estado.libre_grupo(g,d_new,p_new):     continue
                        delta = delta_move(s,r_old,d_old,p_old,
                                           r_new,d_new,p_new,
                                           g,estado,secc_info,sal_cap)
                        if delta < mejor_delta:
                            mejor_delta = delta
                            mejor_slot  = (r_new,d_new,p_new)

            if mejor_slot:
                estado.liberar(s,r_old,d_old,p_old,g)
                estado.asignar(s,*mejor_slot,g)
                mejoro = True

        if not mejoro: break
    return estado


# ══════════════════════════════════════════════════════════════
# 6. LOOP GRASP
# ══════════════════════════════════════════════════════════════
def grasp(df_secc, sal_por_secc, grupo_de_secc, secc_info, sal_cap,
          alpha, n_iter, time_limit, seed=42):
    rng          = random.Random(seed)
    mejor_estado = None
    mejor_fobj   = float('inf')
    historial    = []
    t0           = time.time()

    print(f"\n{'─'*60}")
    print(f"GRASP α={alpha} | máx {n_iter} iter | limit {time_limit}s")
    print(f"{'─'*60}")

    for it in range(1,n_iter+1):
        elapsed = time.time()-t0
        if elapsed >= time_limit:
            print(f"\n  ⏱ Time limit {time_limit}s en iter {it}. Deteniendo.")
            break

        estado = construccion(df_secc,sal_por_secc,grupo_de_secc,
                               secc_info,sal_cap,alpha,rng)
        f_const  = fobj_total(estado,secc_info,sal_cap)

        estado   = busqueda_local(estado,sal_por_secc,grupo_de_secc,
                                   secc_info,sal_cap)
        f_local  = fobj_total(estado,secc_info,sal_cap)

        tag = ''
        if f_local < mejor_fobj:
            mejor_fobj   = f_local
            mejor_estado = estado.clonar()
            tag = '★ NUEVO MEJOR'

        elapsed = time.time()-t0
        print(f"  [{elapsed:5.0f}s] iter {it:>3}/{n_iter} | "
              f"const={f_const:.0f} local={f_local:.0f} "
              f"mejor={mejor_fobj:.0f} {tag}")

        historial.append({'iter':it,'f_construccion':round(f_const,2),
                          'f_local':round(f_local,2),
                          'f_mejor':round(mejor_fobj,2),
                          'tiempo_s':round(elapsed,1)})

    return mejor_estado, mejor_fobj, historial


# ══════════════════════════════════════════════════════════════
# 7. REPORTE Y GUARDADO
# ══════════════════════════════════════════════════════════════
def reportar(mejor_estado, mejor_fobj, historial,
             df_secc, secc_info, sal_cap, nombre, alpha, tiempo_s):
    todas  = set(df_secc['id_seccion'])
    b_req  = df_secc.set_index('id_seccion')['bloques_semanales'].to_dict()
    n_comp = sum(len(mejor_estado.section_slots[s])==b_req[s] for s in todas)
    pct    = n_comp/len(todas)*100
    factible = (pct==100.0)

    # Descomposición
    c_desp = sum(max(0,sal_cap[r]-secc_info[s]['estudiantes_estimados']-UMBRAL_CAP)
                 for s,slots in mejor_estado.section_slots.items() for r,d,p in slots)
    c_huecos = sum(mejor_estado.gaps(g,d)
                   for g,dias in mejor_estado.group_day_periods.items() for d in dias)
    c_exceso = sum(max(0,len(ps)-N_MAX_DIA)
                   for g,dias in mejor_estado.group_day_periods.items()
                   for d,ps in dias.items())
    c_conc_raw = sum(max(0,len(dias)-1) for dias in mejor_estado.section_days.values())
    c_cont_raw = sum(mejor_estado.gaps_seccion(s, d)
                     for s in mejor_estado.section_slots for d in DIAS)
    c_salon_raw = sum(max(0, len(rooms)-1)
                      for dias in mejor_estado.section_day_rooms.values()
                      for rooms in dias.values())
    n_asig = sum(1 for s in mejor_estado.section_slots if mejor_estado.section_slots[s])

    tag = f"a{str(alpha).replace('.','')}"
    print(f"\n{'═'*60}")
    print(f"RESULTADO GRASP α={alpha} — {nombre.upper()}")
    print(f"{'═'*60}")
    print(f"  Tiempo: {tiempo_s:.1f}s | Iteraciones: {len(historial)}")
    print(f"  Secciones: {n_comp}/{len(todas)} ({pct:.1f}%) | {'✅' if factible else '❌'}")
    print(f"  S1={W_DESP*c_desp:.0f}  S2={W_HUECOS*c_huecos:.0f}  "
          f"S3={W_EXCESO*c_exceso:.0f}  S4={W_CONC*c_conc_raw:.0f}  "
          f"S5={W_CONT*c_cont_raw:.0f}  S6={W_SALON*c_salon_raw:.0f}")
    print(f"  Días extra (S4 raw): {c_conc_raw} | "
          f"Huecos intra-asignatura (S5 raw): {c_cont_raw} | "
          f"Salones extra (S6 raw): {c_salon_raw} | f_obj: {mejor_fobj:.2f}")

    dias_s = {s:len(mejor_estado.section_days[s])
              for s in todas if mejor_estado.section_slots[s]}
    if dias_s:
        en_1 = sum(1 for v in dias_s.values() if v==1)
        print(f"  Secciones en 1 día: {en_1}/{n_comp} ({en_1/n_comp*100:.0f}%)")

    # Guardar
    rows = [{'id_seccion':s,'id_salon':r,'dia':NOMBRE_DIA[d],'hora':HORA_PERIODO[p],
             'carrera':secc_info[s]['carrera'],'semestre':secc_info[s]['semestre'],
             'nombre_asignatura':secc_info[s]['nombre_asignatura'],
             'grupo':secc_info[s]['grupo'],'tipo_espacio':secc_info[s]['tipo_espacio'],
             'estudiantes_est':secc_info[s]['estudiantes_estimados']}
            for s,slots in mejor_estado.section_slots.items() for r,d,p in slots]

    pd.DataFrame(rows).to_csv(f"{OUT_DIR}/grasp_v41_{nombre}_{tag}_horario.csv",
                               index=False,encoding='utf-8')

    resumen = {
        'instancia':nombre,'metodo':f'GRASP_a{alpha}','alpha':alpha,
        'status':'COMPLETE' if factible else 'PARTIAL',
        'f_obj':round(mejor_fobj,2),'pct_asignadas':round(pct,1),
        'n_secciones_total':len(todas),'n_secciones_completas':n_comp,
        'n_conflictos_salon':0,'n_conflictos_grupo':0,
        'gap_pct':None,'cota_inferior':None,'tiempo_s':round(tiempo_s,1),
        'factible':factible,
        'c_desp_raw':round(c_desp,1),'c_huecos_raw':round(c_huecos,1),
        'c_exceso_raw':round(c_exceso,1),'c_conc_raw':round(c_conc_raw,1),
        'c_cont_raw':round(c_cont_raw,1),
        'c_salon_raw':round(c_salon_raw,1),
        'n_iteraciones':len(historial),
    }
    pd.DataFrame([resumen]).to_csv(f"{OUT_DIR}/grasp_v41_{nombre}_{tag}_resumen.csv",
                                    index=False,encoding='utf-8')
    pd.DataFrame(historial).to_csv(f"{OUT_DIR}/grasp_v41_{nombre}_{tag}_convergencia.csv",
                                    index=False,encoding='utf-8')
    print(f"  Guardado: resultados/grasp_v41_{nombre}_{tag}_resumen.csv")
    print(f"{'═'*60}")
    return resumen


# ══════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════
def main():
    nombre = sys.argv[1].lower() if len(sys.argv)>1 else 'piloto'
    alpha  = float(sys.argv[2])  if len(sys.argv)>2 else 0.3
    cfg    = INSTANCIAS_CONFIG.get(nombre,{})
    n_iter = int(sys.argv[3])    if len(sys.argv)>3 else cfg.get('n_iter_default',50)
    time_limit = cfg.get('time_limit',120)

    if nombre not in INSTANCIAS_CONFIG:
        print(f"Opciones: {list(INSTANCIAS_CONFIG.keys())}"); sys.exit(1)

    print("="*60)
    print(f"ETAPA 7 — GRASP v4.1  (S4=max(0,n_días−1), S5=continuidad, S6=salón, N_MAX=6)")
    print(f"Instancia={nombre} | α={alpha} | iter={n_iter} | limit={time_limit}s")
    print("="*60)

    df_secc,df_sal,df_compat_secc = cargar_datos(nombre)
    secc_info,sal_cap,sal_por_secc,grupos,grupo_de_secc = \
        precomputar(df_secc,df_sal,df_compat_secc)

    t0 = time.time()
    mejor_estado,mejor_fobj,historial = grasp(
        df_secc,sal_por_secc,grupo_de_secc,secc_info,sal_cap,
        alpha=alpha, n_iter=n_iter, time_limit=time_limit, seed=42)
    tiempo_s = time.time()-t0

    reportar(mejor_estado,mejor_fobj,historial,
             df_secc,secc_info,sal_cap,nombre,alpha,tiempo_s)

if __name__ == "__main__":
    main()
