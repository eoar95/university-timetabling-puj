"""
===============================================================
SCHEDULING ACADÉMICO — JAVERIANA INGENIERÍA
Etapa 5: Modelo exacto Gurobi — v4.1
===============================================================
Cambios respecto a v4.0:
  - Se agrega S6 — Estabilidad de salón intra-asignatura.
    Penaliza usar más de un salón para una misma sección dentro
    del mismo día: C_salon = ∑_{s,d} max(0, n_salones_{s,d} - 1).
  - Peso nuevo: W_SALON = 6.
  - Implementación exacta: variable z_salon[s,r,d] que indica si
    la sección s usa el salón r en el día d.

Uso:
    python etapa5_gurobi_v4_1.py [piloto|mediana|completa]

Salidas (./resultados/):
    gurobi_v41_<instancia>_horario.csv
    gurobi_v41_<instancia>_resumen.csv
===============================================================
"""

import sys, os, time
import pandas as pd

try:
    import gurobipy as gp
    from gurobipy import GRB
except ImportError:
    print("ERROR: gurobipy no instalado.")
    print("  pip install gurobipy")
    sys.exit(1)

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
    'piloto':   {'carreras_fijas':['Bioingeniería'], 'n_carreras':None,
                 'time_limit':120, 'mip_gap':0.00},
    'mediana':  {'carreras_fijas':None, 'n_carreras':4,
                 'time_limit':300, 'mip_gap':0.00},
    'completa': {'carreras_fijas':None, 'n_carreras':None,
                 'time_limit':600, 'mip_gap':0.10},
}
os.makedirs(OUT_DIR, exist_ok=True)


# ══════════════════════════════════════════════════════════════
# 1. CARGA DE DATOS
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
    print(f"\n  Instancia '{nombre}': {len(carreras)} carreras, "
          f"{len(df_secc)} secciones, {df_secc['bloques_semanales'].sum()} bloques")
    return df_secc, df_sal, df_compat_secc, carreras, cfg


# ══════════════════════════════════════════════════════════════
# 2. PRECÓMPUTO
# ══════════════════════════════════════════════════════════════
def precomputar(df_secc, df_sal, df_compat_secc):
    secc_info = df_secc.set_index('id_seccion').to_dict('index')
    sal_cap   = df_sal.set_index('id_salon')['capacidad'].to_dict()

    sal_por_secc = {}
    secc_por_sal = {}
    for _, row in df_compat_secc.iterrows():
        sal_por_secc.setdefault(row['id_seccion'],[]).append(row['id_salon'])
        secc_por_sal.setdefault(row['id_salon'],[]).append(row['id_seccion'])

    pares_compat = list(
        df_compat_secc[['id_seccion','id_salon']].drop_duplicates()
        .itertuples(index=False, name=None))

    grupos = {}
    for _, row in df_secc.iterrows():
        g = (row['carrera'], row['semestre'], row['grupo'])
        grupos.setdefault(g,[]).append(row['id_seccion'])

    return secc_info, sal_cap, sal_por_secc, secc_por_sal, pares_compat, grupos


# ══════════════════════════════════════════════════════════════
# 3. MODELO GUROBI
# ══════════════════════════════════════════════════════════════
def construir_modelo(df_secc, df_sal, df_compat_secc, cfg,
                     secc_info, sal_cap, sal_por_secc, secc_por_sal,
                     pares_compat, grupos):
    t0 = time.time()
    model = gp.Model("scheduling_v41")
    model.setParam('TimeLimit', cfg['time_limit'])
    model.setParam('MIPGap',    cfg['mip_gap'])
    model.setParam('Threads',   4)
    model.setParam('OutputFlag',1)

    # ── Variables principales: x[s,r,d,p] ────────────────────
    x = {(s,r,d,p): model.addVar(vtype=GRB.BINARY, name=f"x_{s}_{r}_{d}_{p}")
         for s,r in pares_compat for d in DIAS for p in PERIODOS}

    # ── S2: before/after/idle por (grupo,dia,periodo) ────────
    before = {(g,d,p): model.addVar(vtype=GRB.BINARY) for g in grupos for d in DIAS for p in PERIODOS}
    after  = {(g,d,p): model.addVar(vtype=GRB.BINARY) for g in grupos for d in DIAS for p in PERIODOS}
    idle   = {(g,d,p): model.addVar(vtype=GRB.BINARY) for g in grupos for d in DIAS for p in PERIODOS}

    # ── S3: exceso[g,d] continua ≥ 0 ─────────────────────────
    exceso = {(g,d): model.addVar(lb=0.0, vtype=GRB.CONTINUOUS)
              for g in grupos for d in DIAS}

    # ── S4 v4.1: y_dia[s,d] binaria — usa sección s el día d ─
    todas_secc = list(df_secc['id_seccion'])
    y_dia = {(s,d): model.addVar(vtype=GRB.BINARY, name=f"yd_{s}_{d}")
             for s in todas_secc for d in DIAS}

    # ── S5 v4.1: continuidad intra-asignatura por sección/día/período ─
    before_sec = {(s,d,p): model.addVar(vtype=GRB.BINARY, name=f"bs_{s}_{d}_{p}")
                  for s in todas_secc for d in DIAS for p in PERIODOS}
    after_sec  = {(s,d,p): model.addVar(vtype=GRB.BINARY, name=f"as_{s}_{d}_{p}")
                  for s in todas_secc for d in DIAS for p in PERIODOS}
    idle_sec   = {(s,d,p): model.addVar(vtype=GRB.BINARY, name=f"is_{s}_{d}_{p}")
                  for s in todas_secc for d in DIAS for p in PERIODOS}

    # ── S6 v4.1: estabilidad de salón intra-asignatura ───────
    # z_salon[s,r,d] = 1 si la sección s usa el salón r en el día d.
    z_salon = {(s,r,d): model.addVar(vtype=GRB.BINARY, name=f"zs_{s}_{r}_{d}")
               for s,r in pares_compat for d in DIAS}

    model.update()
    print(f"\n  Variables x: {len(x):,} | y_dia: {len(y_dia):,} | "
          f"idle_sec: {len(idle_sec):,} | z_salon: {len(z_salon):,} | Total: {model.NumVars:,}")

    # ── H1: completitud ───────────────────────────────────────
    for s in todas_secc:
        rls = sal_por_secc.get(s,[])
        if not rls: continue
        model.addConstr(
            gp.quicksum(x[s,r,d,p] for r in rls for d in DIAS for p in PERIODOS)
            == secc_info[s]['bloques_semanales'])

    # ── H2: no traslape salón ─────────────────────────────────
    for r in df_sal['id_salon']:
        ss = secc_por_sal.get(r,[])
        if not ss: continue
        for d in DIAS:
            for p in PERIODOS:
                model.addConstr(gp.quicksum(x[s,r,d,p] for s in ss) <= 1)

    # ── H3: no traslape grupo ─────────────────────────────────
    for g, ss_g in grupos.items():
        for d in DIAS:
            for p in PERIODOS:
                model.addConstr(
                    gp.quicksum(x[s,r,d,p]
                                for s in ss_g
                                for r in sal_por_secc.get(s,[])) <= 1)

    # ── S2: huecos (before/after/idle) ───────────────────────
    for g, ss_g in grupos.items():
        for d in DIAS:
            for p in PERIODOS:
                y_gdp = gp.quicksum(x[s,r,d,p]
                                    for s in ss_g
                                    for r in sal_por_secc.get(s,[]))
                hasta = gp.quicksum(x[s,r,d,pp]
                                    for s in ss_g
                                    for r in sal_por_secc.get(s,[])
                                    for pp in range(p+1))
                model.addConstr(before[g,d,p] <= hasta)
                model.addConstr(hasta <= 10*before[g,d,p])
                if p < 9:
                    desde = gp.quicksum(x[s,r,d,pp]
                                        for s in ss_g
                                        for r in sal_por_secc.get(s,[])
                                        for pp in range(p+1,10))
                    model.addConstr(after[g,d,p] <= desde)
                    model.addConstr(desde <= 10*after[g,d,p])
                else:
                    model.addConstr(after[g,d,p] == 0)
                model.addConstr(idle[g,d,p] <= before[g,d,p])
                model.addConstr(idle[g,d,p] <= after[g,d,p])
                model.addConstr(idle[g,d,p] <= 1 - y_gdp)
                model.addConstr(idle[g,d,p] >= before[g,d,p]+after[g,d,p]-y_gdp-1)

    # ── S3: exceso carga diaria (N_MAX_DIA=6) ─────────────────
    for g, ss_g in grupos.items():
        for d in DIAS:
            model.addConstr(exceso[g,d] >= gp.quicksum(
                x[s,r,d,p] for s in ss_g
                for r in sal_por_secc.get(s,[]) for p in PERIODOS) - N_MAX_DIA)

    # ── S4 v4.1: concentración diaria ─────────────────────────
    # y_dia[s,d] = 1 si y solo si la sección s tiene al menos un bloque
    # asignado en el día d. En v4.1 se amarra en ambos sentidos porque S6
    # usa el término (z_salon - y_dia) y no conviene dejar y_dia libre.
    for s in todas_secc:
        rls = sal_por_secc.get(s,[])
        if not rls: continue
        for d in DIAS:
            bloques_sd = gp.quicksum(x[s,r,d,p] for r in rls for p in PERIODOS)
            model.addConstr(50*y_dia[s,d] >= bloques_sd)
            model.addConstr(y_dia[s,d] <= bloques_sd)

    # ── S5 v4.1: continuidad intra-asignatura ─────────────────
    # idle_sec[s,d,p] = 1 si el período p está vacío entre el primer
    # y último bloque de la misma sección s en el día d.
    for s in todas_secc:
        rls = sal_por_secc.get(s,[])
        if not rls: continue
        for d in DIAS:
            for p in PERIODOS:
                y_sdp = gp.quicksum(x[s,r,d,p] for r in rls)
                hasta = gp.quicksum(x[s,r,d,pp]
                                    for r in rls for pp in range(p+1))
                model.addConstr(before_sec[s,d,p] <= hasta)
                model.addConstr(hasta <= 10*before_sec[s,d,p])
                if p < 9:
                    desde = gp.quicksum(x[s,r,d,pp]
                                        for r in rls for pp in range(p+1,10))
                    model.addConstr(after_sec[s,d,p] <= desde)
                    model.addConstr(desde <= 10*after_sec[s,d,p])
                else:
                    model.addConstr(after_sec[s,d,p] == 0)
                model.addConstr(idle_sec[s,d,p] <= before_sec[s,d,p])
                model.addConstr(idle_sec[s,d,p] <= after_sec[s,d,p])
                model.addConstr(idle_sec[s,d,p] <= 1 - y_sdp)
                model.addConstr(idle_sec[s,d,p] >= before_sec[s,d,p]+after_sec[s,d,p]-y_sdp-1)

    # ── S6 v4.1: estabilidad de salón intra-asignatura ────────
    # Si una sección usa el salón r en cualquier período del día d,
    # entonces z_salon[s,r,d] debe activarse. Como z_salon entra con
    # costo positivo en el objetivo, el modelo lo mantiene en 0 cuando
    # no se usa ese salón.
    for s,r in pares_compat:
        b_s = secc_info[s]['bloques_semanales']
        for d in DIAS:
            model.addConstr(
                gp.quicksum(x[s,r,d,p] for p in PERIODOS) <= b_s * z_salon[s,r,d]
            )

    model.update()
    print(f"  Restricciones: {model.NumConstrs:,} | "
          f"Construido en {time.time()-t0:.1f}s")

    # ── Función objetivo v4.1 ─────────────────────────────────
    # S4: C_conc = ∑_s max(0, n_días_s − 1) = ∑_{s,d} y_dia[s,d] − |S|
    # El término −|S| es constante → no altera la solución óptima,
    # pero hace que f_obj = 0 sea el ideal teórico.
    n_secc = len(todas_secc)   # ← v4.1: constante para corrección S4
    model.setObjective(
        W_DESP * gp.quicksum(
            max(0, sal_cap[r]-secc_info[s]['estudiantes_estimados']-UMBRAL_CAP)
            * x[s,r,d,p]
            for s,r in pares_compat for d in DIAS for p in PERIODOS)
        + W_HUECOS * gp.quicksum(
            idle[g,d,p] for g in grupos for d in DIAS for p in PERIODOS)
        + W_EXCESO * gp.quicksum(
            exceso[g,d] for g in grupos for d in DIAS)
        + W_CONC * (gp.quicksum(
            y_dia[s,d] for s in todas_secc for d in DIAS)
            - n_secc)                                     # primer día gratis
        + W_CONT * gp.quicksum(                           # S5 v4.1
            idle_sec[s,d,p] for s in todas_secc for d in DIAS for p in PERIODOS)
        + W_SALON * (                                      # S6 v4.1
            gp.quicksum(z_salon[s,r,d] for s,r in pares_compat for d in DIAS)
            - gp.quicksum(y_dia[s,d] for s in todas_secc for d in DIAS)),
        GRB.MINIMIZE
    )

    return model, x, idle, exceso, y_dia, idle_sec, z_salon, grupos, sal_por_secc, todas_secc


# ══════════════════════════════════════════════════════════════
# 4. RESULTADOS
# ══════════════════════════════════════════════════════════════
def extraer_resultados(model, x, idle, exceso, y_dia, idle_sec, z_salon,
                       df_secc, df_sal, grupos, sal_por_secc,
                       secc_info, sal_cap, pares_compat, todas_secc,
                       nombre, tiempo_s):

    STATUS_MAP = {GRB.OPTIMAL:'OPTIMAL', GRB.TIME_LIMIT:'TIME_LIMIT',
                  GRB.INFEASIBLE:'INFEASIBLE'}
    status = STATUS_MAP.get(model.Status, f"STATUS_{model.Status}")
    print(f"\n{'═'*60}\nRESULTADOS — {nombre.upper()}\n{'═'*60}")
    print(f"  Status: {status} | Tiempo: {tiempo_s:.1f}s")

    if model.Status == GRB.INFEASIBLE or model.SolCount == 0:
        print("  ⚠ Sin solución disponible")
        pd.DataFrame([{'instancia':nombre,'metodo':'Gurobi','status':status,
                        'tiempo_s':round(tiempo_s,1),'factible':False}])\
          .to_csv(f"{OUT_DIR}/gurobi_v41_{nombre}_resumen.csv", index=False)
        return {}

    obj_val = model.ObjVal
    gap_pct = model.MIPGap * 100
    print(f"  f_obj: {obj_val:.2f} | Gap: {gap_pct:.4f}% | Cota: {model.ObjBound:.2f}")

    # Asignaciones
    rows = [(s,r,d,p) for (s,r,d,p),v in x.items() if v.X > 0.5]
    df_h = pd.DataFrame([{
        'id_seccion':s,'id_salon':r,
        'dia':NOMBRE_DIA[d],'hora':HORA_PERIODO[p],
        'carrera':secc_info[s]['carrera'],'semestre':secc_info[s]['semestre'],
        'nombre_asignatura':secc_info[s]['nombre_asignatura'],
        'grupo':secc_info[s]['grupo'],'tipo_espacio':secc_info[s]['tipo_espacio'],
        'estudiantes_est':secc_info[s]['estudiantes_estimados'],
        'cap_salon':sal_cap.get(r,'?')
    } for s,r,d,p in rows])

    # Métricas H1
    n_total = len(todas_secc)
    b_req   = df_secc.set_index('id_seccion')['bloques_semanales'].to_dict()
    b_asig  = df_h.groupby('id_seccion').size() if len(df_h) else {}
    n_comp  = sum(b_asig.get(s,0)==b_req[s] for s in todas_secc)
    pct     = n_comp/n_total*100

    # Métricas H2/H3
    n_cs = n_cg = 0
    if len(df_h):
        n_cs = int((df_h.groupby(['id_salon','dia','hora']).size()>1).sum())
        df_h['gk'] = df_h['carrera']+'_'+df_h['semestre'].astype(str)+'_'+df_h['grupo'].astype(str)
        n_cg = int((df_h.groupby(['gk','dia','hora']).size()>1).sum())
    factible = (pct==100.0 and n_cs==0 and n_cg==0)

    # Descomposición
    c_desp   = sum(max(0,sal_cap.get(r,'?')-secc_info[s]['estudiantes_estimados']-UMBRAL_CAP)
                   for s,r,d,p in rows)
    c_huecos = sum(idle[g,d,p].X for g in grupos for d in DIAS for p in PERIODOS
                   if idle[g,d,p].X>0.5)
    c_exceso = sum(exceso[g,d].X for g in grupos for d in DIAS)

    # S4 v4.1: c_conc_raw = días extra = ∑_s max(0, n_días_s − 1)
    c_conc_raw = sum(max(0, sum(y_dia[s,d].X for d in DIAS) - 1)
                     for s in todas_secc)

    # S5 v4.1: huecos internos de una misma sección en un mismo día
    c_cont_raw = sum(idle_sec[s,d,p].X for s in todas_secc for d in DIAS for p in PERIODOS
                     if idle_sec[s,d,p].X > 0.5)

    # S6 v4.1: salones extra usados por una misma sección en un mismo día
    c_salon_raw = sum(max(0, sum(z_salon[s,r,d].X for r in sal_por_secc.get(s,[])) - 1)
                      for s in todas_secc for d in DIAS)

    print(f"\n  Secciones: {n_comp}/{n_total} ({pct:.1f}%) | "
          f"Conflictos salón={n_cs} grupo={n_cg} | Factible={'✅' if factible else '❌'}")
    print(f"  S1={W_DESP*c_desp:.0f}  S2={W_HUECOS*c_huecos:.0f}  "
          f"S3={W_EXCESO*c_exceso:.0f}  S4={W_CONC*c_conc_raw:.0f}  "
          f"S5={W_CONT*c_cont_raw:.0f}  S6={W_SALON*c_salon_raw:.0f}")
    print(f"  f_obj (verificación): "
          f"{W_DESP*c_desp + W_HUECOS*c_huecos + W_EXCESO*c_exceso + W_CONC*c_conc_raw + W_CONT*c_cont_raw + W_SALON*c_salon_raw:.2f}")
    print(f"  Días extra (S4 raw): {c_conc_raw:.0f} | Huecos intra-asignatura (S5 raw): {c_cont_raw:.0f} | Salones extra (S6 raw): {c_salon_raw:.0f}")

    # Estadística de concentración
    if len(df_h):
        dias_s = df_h.groupby('id_seccion')['dia'].nunique()
        en_1 = (dias_s==1).sum()
        print(f"  Secciones en 1 día: {en_1} ({en_1/n_comp*100:.0f}%) | "
              f"2 días: {(dias_s==2).sum()} | 3+: {(dias_s>=3).sum()}")

    # Guardar
    if len(df_h):
        df_h.drop(columns=['gk'],errors='ignore')\
            .to_csv(f"{OUT_DIR}/gurobi_v41_{nombre}_horario.csv", index=False)

    resumen = {
        'instancia':nombre,'metodo':'Gurobi','status':status,
        'f_obj':round(obj_val,2),'pct_asignadas':round(pct,1),
        'n_secciones_total':n_total,'n_secciones_completas':n_comp,
        'n_conflictos_salon':n_cs,'n_conflictos_grupo':n_cg,
        'gap_pct':round(gap_pct,4),'cota_inferior':round(model.ObjBound,2),
        'tiempo_s':round(tiempo_s,1),'factible':factible,
        'c_desp_raw':round(c_desp,1),'c_huecos_raw':round(c_huecos,1),
        'c_exceso_raw':round(c_exceso,1),'c_conc_raw':round(c_conc_raw,1),
        'c_cont_raw':round(c_cont_raw,1),
        'c_salon_raw':round(c_salon_raw,1),
    }
    pd.DataFrame([resumen]).to_csv(
        f"{OUT_DIR}/gurobi_v41_{nombre}_resumen.csv", index=False)
    print(f"  Guardado: resultados/gurobi_v41_{nombre}_resumen.csv")
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
    print("ETAPA 5 — GUROBI v4.1")
    print(f"S4=max(0,n_días−1)·w4  |  S5=continuidad·w5  |  S6=salón·w6  |  N_MAX_DIA=6  |  Instancia={nombre}")
    print("="*60)

    df_secc,df_sal,df_compat_secc,carreras,cfg = cargar_datos(nombre)
    secc_info,sal_cap,sal_por_secc,secc_por_sal,pares_compat,grupos = \
        precomputar(df_secc,df_sal,df_compat_secc)

    model,x,idle,exceso,y_dia,idle_sec,z_salon,grupos,sal_por_secc,todas_secc = \
        construir_modelo(df_secc,df_sal,df_compat_secc,cfg,
                         secc_info,sal_cap,sal_por_secc,secc_por_sal,
                         pares_compat,grupos)

    print(f"\n{'─'*60}\nOPTIMIZACIÓN\n{'─'*60}")
    t0 = time.time()
    model.optimize()
    tiempo_s = time.time()-t0

    extraer_resultados(model,x,idle,exceso,y_dia,idle_sec,z_salon,
                       df_secc,df_sal,grupos,sal_por_secc,
                       secc_info,sal_cap,pares_compat,todas_secc,
                       nombre,tiempo_s)

if __name__ == "__main__":
    main()
