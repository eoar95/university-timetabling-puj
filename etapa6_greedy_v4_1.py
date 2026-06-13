"""
===============================================================
SCHEDULING ACADÉMICO — JAVERIANA INGENIERÍA
Etapa 6: Heurística Greedy — v4.1
===============================================================
Cambios respecto a v4.0:
  - Se agrega S5 — Continuidad intra-asignatura.
    Penaliza huecos internos entre bloques de la misma sección
    dentro del mismo día.
    Fórmula: C_cont = ∑_{s,d} max(0, span_{s,d} − bloques_{s,d})
    donde span_{s,d} = p_ultimo_{s,d} − p_primero_{s,d} + 1.
    Peso: W_CONT = 5.
    Implementación: costo incremental delta_continuidad(s,d,p)
    calculado sobre periodos actuales de la sección en el día.

  - Se agrega S6 — Estabilidad de salón intra-asignatura.
    Penaliza usar más de un salón para una misma sección dentro
    del mismo día.
    Fórmula: C_salon = ∑_{s,d} max(0, n_salones_{s,d} − 1)
    Peso: W_SALON = 6.
    Implementación: costo incremental c_salon en costo_greedy;
    EstadoHorario.section_day_rooms[s][d] rastrea el conjunto de
    salones usados por la sección s en cada día d.

Pesos finales v4.1:
    W_DESP=1, W_HUECOS=2, W_EXCESO=3, W_CONC=4, W_CONT=5, W_SALON=6

Uso:
    python etapa6_greedy_v4_1.py [piloto|mediana|completa]

Salidas (./resultados/):
    greedy_v41_<instancia>_horario.csv
    greedy_v41_<instancia>_resumen.csv
===============================================================
"""

import sys, os, time
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

NOMBRE_DIA   = {0:'Lunes',1:'Martes',2:'Miércoles',3:'Jueves',4:'Viernes'}
HORA_PERIODO = {i:f"{7+i}:00-{8+i}:00" for i in range(10)}
DATA_DIR="C:\\Users\\eoar9\\Documents\\Visual Studio\\01 Universidad\\Optimizacion\\Proyecto Final"
OUT_DIR='resultados'

INSTANCIAS_CONFIG = {
    'piloto':   {'carreras_fijas':['Bioingeniería'], 'n_carreras':None},
    'mediana':  {'carreras_fijas':None, 'n_carreras':4},
    'completa': {'carreras_fijas':None, 'n_carreras':None},
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
        sal_por_secc[s].sort(key=lambda r: sal_cap.get(r,9999) - est)

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

    def gaps(self, g, d):
        ps = self.group_day_periods[g][d]
        return (max(ps)-min(ps)+1-len(ps)) if len(ps)>=2 else 0

    def delta_huecos(self, g, d, p):
        ps = self.group_day_periods[g][d]
        if not ps: return 0
        gaps_antes = (max(ps)-min(ps)+1-len(ps)) if len(ps)>=2 else 0
        nm = min(min(ps),p); nx = max(max(ps),p)
        gaps_nuevo = (nx-nm+1)-(len(ps)+1)
        return gaps_nuevo - gaps_antes

    def bloques_en_dia(self, g, d):
        return len(self.group_day_periods[g][d])

    def periodos_seccion(self, s, d):
        return [p for r2,d2,p in self.section_slots[s] if d2 == d]

    def gaps_seccion(self, s, d):
        ps = self.periodos_seccion(s, d)
        return (max(ps)-min(ps)+1-len(ps)) if len(ps)>=2 else 0

    def delta_continuidad(self, s, d, p):
        ps = self.periodos_seccion(s, d)
        if not ps:
            return 0
        gaps_antes = (max(ps)-min(ps)+1-len(ps)) if len(ps)>=2 else 0
        nm = min(min(ps), p); nx = max(max(ps), p)
        gaps_nuevo = (nx-nm+1) - (len(ps)+1)
        return gaps_nuevo - gaps_antes


# ══════════════════════════════════════════════════════════════
# 3. COSTO GREEDY LOCAL (v4.1 — S4 corregido: primer día gratis)
# ══════════════════════════════════════════════════════════════
def costo_greedy(s, r, d, p, g, estado, secc_info, sal_cap):
    est_s = secc_info[s]['estudiantes_estimados']

    # S1: desperdicio de capacidad
    c_desp = max(0, sal_cap[r] - est_s - UMBRAL_CAP)

    # S2: impacto en huecos del grupo ese día
    c_huecos = estado.delta_huecos(g, d, p)

    # S3: exceso de carga diaria del grupo
    c_exceso = max(0, estado.bloques_en_dia(g, d) + 1 - N_MAX_DIA)

    # S4: penalizar solo cuando d es un día NUEVO para s
    # y s ya tiene al menos un día asignado (primer día = gratis).
    c_conc = 1 if estado.section_days[s] and d not in estado.section_days[s] else 0

    # S5: continuidad intra-asignatura.
    # Mide huecos internos de la misma sección dentro del día d.
    c_cont = estado.delta_continuidad(s, d, p)

    # S6 v4.1: penaliza usar un salón nuevo para la sección dentro del mismo día.
    c_salon = 1 if estado.section_day_rooms[s][d] and r not in estado.section_day_rooms[s][d] else 0

    return (W_DESP*c_desp + W_HUECOS*c_huecos + W_EXCESO*c_exceso +
            W_CONC*c_conc + W_CONT*c_cont + W_SALON*c_salon)


# ══════════════════════════════════════════════════════════════
# 4. ORDENAMIENTO (más restringida primero)
# ══════════════════════════════════════════════════════════════
def ordenar_secciones(df_secc, sal_por_secc, secc_info):
    secs = list(df_secc['id_seccion'])
    secs.sort(key=lambda s: (
        -secc_info[s]['bloques_semanales'] / max(len(sal_por_secc[s]),1),
        -secc_info[s]['bloques_semanales'], s))
    return secs


# ══════════════════════════════════════════════════════════════
# 5. CONSTRUCCIÓN GREEDY
# ══════════════════════════════════════════════════════════════
def construir_greedy(df_secc, sal_por_secc, grupo_de_secc, secc_info, sal_cap):
    estado    = EstadoHorario()
    secciones = ordenar_secciones(df_secc, sal_por_secc, secc_info)
    no_asig   = []
    n = len(secciones)

    for i, s in enumerate(secciones):
        b_s = secc_info[s]['bloques_semanales']
        g   = grupo_de_secc[s]
        sal = sal_por_secc[s]

        if (i+1) % 150 == 0 or i == n-1:
            print(f"  Progreso: {i+1}/{n}...", end='\r')

        for _ in range(b_s):
            mejor_costo = float('inf')
            mejor_slot  = None

            # Priorizar días ya usados por esta sección (S4 = 0 costo)
            dias_usados  = sorted(estado.section_days[s],
                                  key=lambda d: (estado.bloques_en_dia(g,d), d))
            dias_nuevos  = sorted([d for d in DIAS if d not in estado.section_days[s]],
                                  key=lambda d: (estado.bloques_en_dia(g,d), d))
            dias_ordenados = dias_usados + dias_nuevos

            for d in dias_ordenados:
                for p in PERIODOS:
                    if not estado.libre_grupo(g, d, p): continue
                    for r in sal:
                        if not estado.libre_salon(r, d, p): continue
                        costo = costo_greedy(s, r, d, p, g, estado, secc_info, sal_cap)
                        if (costo, d, p, r) < (mejor_costo,
                                               *(mejor_slot[1:] if mejor_slot else (99,99,'z'))):
                            mejor_costo = costo
                            mejor_slot  = (r, d, p)

            if mejor_slot:
                estado.asignar(s, *mejor_slot, g)
            else:
                no_asig.append(s)

    print()
    return estado, no_asig


# ══════════════════════════════════════════════════════════════
# 6. CÁLCULO f_obj (v4.1 — fórmula corregida: c_conc_raw directo)
# ══════════════════════════════════════════════════════════════
def calcular_fobj(estado, secc_info, sal_cap):
    c_desp = sum(max(0, sal_cap[r]-secc_info[s]['estudiantes_estimados']-UMBRAL_CAP)
                 for s,slots in estado.section_slots.items() for r,d,p in slots)

    c_huecos = sum(estado.gaps(g,d)
                   for g,dias in estado.group_day_periods.items() for d in dias)

    c_exceso = sum(max(0, len(ps)-N_MAX_DIA)
                   for g,dias in estado.group_day_periods.items()
                   for d,ps in dias.items())

    # S4: C_conc = ∑_s max(0, n_días_s − 1)
    c_conc_raw = sum(max(0, len(dias)-1) for dias in estado.section_days.values())

    # S5: continuidad intra-asignatura = huecos internos por sección/día
    c_cont_raw = sum(estado.gaps_seccion(s, d)
                     for s in estado.section_slots for d in DIAS)

    # S6 v4.1: salones extra usados por una misma sección dentro del mismo día
    c_salon_raw = sum(max(0, len(rooms)-1)
                      for dias in estado.section_day_rooms.values()
                      for rooms in dias.values())

    n_asig     = sum(1 for s in estado.section_slots if estado.section_slots[s])  # solo reporte

    f = (W_DESP*c_desp + W_HUECOS*c_huecos + W_EXCESO*c_exceso +
         W_CONC*c_conc_raw + W_CONT*c_cont_raw + W_SALON*c_salon_raw)
    return f, c_desp, c_huecos, c_exceso, c_conc_raw, c_cont_raw, c_salon_raw, n_asig


# ══════════════════════════════════════════════════════════════
# 7. REPORTE Y GUARDADO
# ══════════════════════════════════════════════════════════════
def reportar(estado, no_asig, df_secc, secc_info, sal_cap, nombre, tiempo_s):
    todas    = set(df_secc['id_seccion'])
    b_req    = df_secc.set_index('id_seccion')['bloques_semanales'].to_dict()
    n_comp   = sum(len(estado.section_slots[s])==b_req[s] for s in todas)
    pct      = n_comp/len(todas)*100
    factible = (pct==100.0)

    f, c_desp, c_huecos, c_exceso, c_conc_raw, c_cont_raw, c_salon_raw, n_asig = calcular_fobj(estado, secc_info, sal_cap)

    print(f"\n{'═'*60}")
    print(f"RESULTADOS GREEDY v4.1 — {nombre.upper()}")
    print(f"{'═'*60}")
    print(f"  Tiempo:           {tiempo_s:.2f} s")
    print(f"  Secciones:        {n_comp}/{len(todas)} ({pct:.1f}%)")
    print(f"  Factible:         {'✅' if factible else '❌'}")
    print(f"\n  S1 Desp  (×{W_DESP}):   {W_DESP*c_desp:>8.1f}   (raw={c_desp:.0f})")
    print(f"  S2 Huecos(×{W_HUECOS}):   {W_HUECOS*c_huecos:>8.1f}   (raw={c_huecos:.0f})")
    print(f"  S3 Exceso(×{W_EXCESO}):   {W_EXCESO*c_exceso:>8.1f}   (raw={c_exceso:.0f})")
    print(f"  S4 Conc  (×{W_CONC}):   {W_CONC*c_conc_raw:>8.1f}   (días_extra={c_conc_raw:.0f})")
    print(f"  S5 Cont  (×{W_CONT}):   {W_CONT*c_cont_raw:>8.1f}   (huecos_sec={c_cont_raw:.0f})")
    print(f"  S6 Salón (×{W_SALON}):  {W_SALON*c_salon_raw:>8.1f}   (salones_extra={c_salon_raw:.0f})")
    print(f"  TOTAL f(x):       {f:>8.2f}")

    # Estadística de concentración
    dias_por_secc = {s: len(estado.section_days[s])
                     for s in todas if estado.section_slots[s]}
    if dias_por_secc:
        en_1 = sum(1 for v in dias_por_secc.values() if v==1)
        en_2 = sum(1 for v in dias_por_secc.values() if v==2)
        en_3 = sum(1 for v in dias_por_secc.values() if v>=3)
        print(f"\n  ── Concentración diaria (S4 v4.1) ───────")
        print(f"  Secciones en 1 día:  {en_1} / {n_comp} ({en_1/n_comp*100:.0f}%)")
        print(f"  Secciones en 2 días: {en_2}")
        print(f"  Secciones en 3+ días:{en_3}")

    # Guardar horario
    rows = [{'id_seccion':s,'id_salon':r,'dia':NOMBRE_DIA[d],'hora':HORA_PERIODO[p],
             'carrera':secc_info[s]['carrera'],'semestre':secc_info[s]['semestre'],
             'nombre_asignatura':secc_info[s]['nombre_asignatura'],
             'grupo':secc_info[s]['grupo'],'tipo_espacio':secc_info[s]['tipo_espacio'],
             'estudiantes_est':secc_info[s]['estudiantes_estimados']}
            for s,slots in estado.section_slots.items() for r,d,p in slots]
    pd.DataFrame(rows).to_csv(f"{OUT_DIR}/greedy_v41_{nombre}_horario.csv",
                               index=False, encoding='utf-8')

    resumen = {
        'instancia':nombre,'metodo':'Greedy','status':'COMPLETE' if factible else 'PARTIAL',
        'f_obj':round(f,2),'pct_asignadas':round(pct,1),
        'n_secciones_total':len(todas),'n_secciones_completas':n_comp,
        'n_conflictos_salon':0,'n_conflictos_grupo':0,
        'gap_pct':None,'cota_inferior':None,'tiempo_s':round(tiempo_s,2),
        'factible':factible,
        'c_desp_raw':round(c_desp,1),'c_huecos_raw':round(c_huecos,1),
        'c_exceso_raw':round(c_exceso,1),'c_conc_raw':round(c_conc_raw,1),
        'c_cont_raw':round(c_cont_raw,1),
        'c_salon_raw':round(c_salon_raw,1),
    }
    pd.DataFrame([resumen]).to_csv(f"{OUT_DIR}/greedy_v41_{nombre}_resumen.csv",
                                    index=False, encoding='utf-8')
    print(f"\n  Guardado: resultados/greedy_v41_{nombre}_resumen.csv")
    print(f"{'═'*60}")
    return resumen


# ══════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════
def main():
    nombre = sys.argv[1].lower() if len(sys.argv)>1 else 'piloto'
    if nombre not in INSTANCIAS_CONFIG:
        print(f"Opciones: {list(INSTANCIAS_CONFIG.keys())}"); sys.exit(1)

    print("="*60)
    print("ETAPA 6 — GREEDY v4.1  (S4=max(0,n_días−1), S5=continuidad, S6=salón, N_MAX=6)")
    print(f"Instancia: {nombre}")
    print("="*60)

    df_secc, df_sal, df_compat_secc = cargar_datos(nombre)
    secc_info, sal_cap, sal_por_secc, grupos, grupo_de_secc = \
        precomputar(df_secc, df_sal, df_compat_secc)

    print(f"\n{'─'*60}\nCONSTRUCCIÓN GREEDY\n{'─'*60}")
    t0 = time.time()
    estado, no_asig = construir_greedy(
        df_secc, sal_por_secc, grupo_de_secc, secc_info, sal_cap)
    tiempo_s = time.time()-t0
    print(f"  Completado en {tiempo_s:.2f}s")
    if no_asig:
        print(f"  ⚠ {len(set(no_asig))} secciones con bloques sin asignar")

    reportar(estado, no_asig, df_secc, secc_info, sal_cap, nombre, tiempo_s)

if __name__ == "__main__":
    main()
