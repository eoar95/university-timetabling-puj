# Optimización de Horarios Académicos en Ingeniería — PUJ

> Comparación de Método Exacto (Gurobi MIP) · Heurística (Greedy) · Metaheurística (GRASP)  
> Maestría en Business Intelligence & Analytics — Pontificia Universidad Javeriana · Junio 2026

---

## Hallazgos principales

| Instancia | Mejor método | f_obj | Tiempo |
|---|---|---|---|
| Piloto (98 secciones) | GRASP α=0.1 | 486 | 0.22 s |
| Mediana (386 secciones) | **Greedy** | **2,641** | **0.85 s** |
| Completa (784 secciones) | **Greedy** | **6,668** | **1.38 s** |

**Gurobi (v4.1):** gap >80% en piloto · gap >92% en mediana · ❌ sin solución factible en instancia completa (600 s).

> El 94% de la diferencia entre Greedy y GRASP se explica por un solo criterio: **S4 — concentración diaria de bloques** (w=4). Greedy lo controla de forma natural gracias a su orden de asignación determinista. GRASP, con su aleatoriedad en la RCL, dispersa los bloques entre días y ninguna búsqueda local individual lo repara.

---

## El problema

Asignación de **784 secciones** de 8 carreras de Ingeniería a **71 salones** (aulas, laboratorios, cómputo) en **50 franjas horarias** (lunes–viernes, 7:00–17:00), respetando restricciones de capacidad, software requerido, tipo de espacio y concentración temporal de bloques.

Es una instancia del **Curriculum-Based Course Timetabling Problem (CB-CTT)** — variante del UCTP donde los conflictos se derivan del currículo semestral publicado [Di Gaspero et al., 2007; Bettinelli et al., 2015].

**Complejidad:** ~2.8 millones de variables binarias en instancia completa · Problema NP-hard [Babaei et al., 2015].

---

## Metodología

### Datos
- **Reales:** planes de estudio PUJ (Excel), edificios y laboratorios (javeriana.edu.co)
- **Supuestos documentados:** capacidades de salón (estándares nacionales, Decreto 1330/2019), software por tipo de asignatura

### Variable de decisión
```
x[s, r, d, p] ∈ {0, 1}
= 1 si la sección s se asigna al salón r, el día d, en el período p
```

### Restricciones duras
- **H1** Completitud — cada sección recibe exactamente `b_s` bloques
- **H2** No traslape de salón — un salón, una clase por franja
- **H3** No traslape de grupo — sin solapamiento dentro del mismo semestre
- **H4** Compatibilidad — solo pares (sección, salón) compatibles en tipo y software

### Función objetivo (6 criterios ponderados)
```
min f(x) = 1·S1 + 2·S2 + 3·S3 + 4·S4 + 5·S5 + 6·S6
```

| Criterio | Descripción |
|---|---|
| S1 | Desperdicio de capacidad (grupos pequeños en salones grandes) |
| S2 | Huecos en el día (ventanas libres entre clases) |
| S3 | Exceso de carga diaria (>6 horas en un día) |
| S4 | Concentración diaria (asignatura en más de 1 día/semana) ⭐ |
| S5 | Continuidad intra-clase (bloques no consecutivos) |
| S6 | Estabilidad de salón (2+ salones distintos para la misma asignatura) |

### Métodos implementados

**Gurobi (MIP exacto)**
- Modelo MILP completo con todas las restricciones
- Time limits: 120 s (piloto) / 300 s (mediana) / 600 s (completa)
- Implementado con `gurobipy`

**Greedy (constructivo)**
- Priorización por score = créditos / salones compatibles (más restringido primero)
- Evaluación de costo incremental O(1) por slot
- Determinista y reproducible

**GRASP (metaheurística)**
- Fase constructiva con RCL y α ∈ {0.1, 0.2, 0.3}
- Búsqueda local: movimientos de 1 bloque, máx. 3 pasadas
- Multistart hasta agotar time limit

---

## Estructura del repositorio

```
scheduling-puj/
├── README.md
├── article/
│   └── articulo_academico_corregido.md   ← artículo académico completo
├── presentation/
│   └── scheduling_puj.pptx                ← presentación 20 slides
└── scripts/
    ├── gurobi_model.py                    ← modelo MIP exacto
    ├── greedy.py                          ← heurística constructiva
    └── grasp.py                           ← metaheurística GRASP
```

---

## Referencias clave

1. Feo, T.A. & Resende, M.G.C. (1995). GRASP. *J. Global Optimization*, 6(2), 109–133.
2. Di Gaspero, L., McCollum, B. & Schaerf, A. (2007). ITC-2007 CB-CTT. *PATAT Tech. Report QUB.*
3. Bettinelli, A. et al. (2015). Overview of CB-CTT. *TOP*, 23(2), 313–349.
4. Rappos, E. et al. (2022). MIP para UCTP — 2.° lugar ITC-2019. *J. Scheduling*, 25, 391–404.
5. Ceschia, S., Di Gaspero, L. & Schaerf, A. (2023). Educational Timetabling. *EJOR*, 308(1), 1–18.

Lista completa de 12 referencias verificadas → [`article/articulo_academico_corregido.md`](article/articulo_academico_corregido.md)

---

## Autor

**Edgar** — Operaciones Analytics & Business Performance | O2C · BI · Transformación Operativa LATAM  
Maestría en Business Intelligence & Analytics — Pontificia Universidad Javeriana, Bogotá  

[![LinkedIn](https://img.shields.io/badge/LinkedIn-Connect-blue)](https://www.linkedin.com/in/eoar95)
