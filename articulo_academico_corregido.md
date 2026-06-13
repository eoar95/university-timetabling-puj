# Comparación de métodos exactos, heurísticos y metaheurísticos para la programación de horarios académicos en carreras de Ingeniería: caso Pontificia Universidad Javeriana Bogotá

**Autores:** Edgar Ayala — Maestría en Business Intelligence & Analytics / Inteligencia Artificial, Pontificia Universidad Javeriana Bogotá

**Curso:** Modelos de Optimización Avanzada | **Fecha:** Junio 2026

---

## Resumen

La programación de horarios académicos es un problema clásico de optimización combinatoria (NP-hard) que conecta la oferta curricular, la infraestructura física y las restricciones operativas de una institución universitaria. Este trabajo compara tres enfoques de solución —un modelo exacto con Gurobi (MIP), una heurística constructiva greedy y una metaheurística GRASP— aplicados a una instancia real de las carreras de Ingeniería de la Pontificia Universidad Javeriana Bogotá. La instancia completa incluye 8 carreras, 784 secciones, 71 salones y 2,198 bloques semanales requeridos en un horizonte de lunes a viernes de 7:00 a.m. a 5:00 p.m. La función objetivo penaliza seis criterios de calidad: desperdicio de capacidad, huecos en el horario, exceso de carga diaria, dispersión temporal de asignaturas, falta de continuidad intra-clase y cambios de salón en el mismo día. Los resultados muestran que la heurística greedy obtiene el mejor balance calidad-tiempo en instancias medianas y completas, mientras que GRASP supera al greedy únicamente en la instancia piloto. El modelo exacto no logra solución factible para la instancia completa dentro del límite de 600 segundos, evidenciando la pérdida de escalabilidad al incorporar restricciones operativas realistas. Estos hallazgos destacan la importancia del diseño de la función objetivo y del presupuesto computacional en la selección de algoritmos para problemas de scheduling académico.

**Palabras clave:** programación de horarios universitarios, GRASP, heurística greedy, Gurobi, optimización combinatoria, CB-CTT.

---

## 1. Introducción

La asignación de horarios académicos es una actividad crítica en instituciones de educación superior. Su aparente simplicidad operativa contrasta con la alta complejidad computacional subyacente: cada asignatura debe colocarse en una franja horaria y un salón compatibles, respetando restricciones de capacidad, disponibilidad, software especializado y ausencia de conflictos entre grupos. Cuando esta tarea se escala a una facultad completa con múltiples carreras, semestres y grupos, el número de combinaciones posibles crece exponencialmente.

En el caso de las carreras de Ingeniería de la Pontificia Universidad Javeriana Bogotá, el problema resulta especialmente rico: los planes de estudio incluyen asignaturas con distintos requerimientos de espacio (aulas, laboratorios, salas de cómputo) y software especializado (MATLAB, FlexSim, GNS3, SolidWorks, entre otros), y la infraestructura disponible abarca 71 espacios distribuidos en varios edificios del campus. Programar simultáneamente 8 carreras, 8 semestres por carrera, 2 grupos por semestre y el conjunto de asignaturas de cada plan de estudios genera una instancia con 784 secciones y más de 2.7 millones de variables binarias solo en la formulación de bloque a bloque.

Este trabajo se enmarca dentro del campo del **University Course Timetabling Problem (UCTP)** y más específicamente del **Curriculum-Based Course Timetabling (CB-CTT)** [Bettinelli et al., 2015], donde los conflictos se derivan directamente del currículo semestral. El objetivo principal no es simplemente construir un horario, sino comparar qué tan efectivos son tres enfoques de distinta naturaleza —un método exacto, una heurística y una metaheurística— en cuanto a calidad de solución, factibilidad y tiempo computacional, cuando se incorporan criterios operativos realistas.

**Pregunta de investigación:** ¿Qué tan efectivos son un modelo exacto con Gurobi, una heurística constructiva greedy y una metaheurística GRASP para resolver un problema de scheduling académico de carreras de Ingeniería de la PUJ, considerando salones, capacidad, software requerido, disponibilidad horaria, carga semanal por créditos y concentración temporal de bloques?

El resto del artículo se organiza así: la Sección 2 presenta la revisión de literatura, la Sección 3 describe la metodología (datos, formulación y métodos), la Sección 4 reporta los resultados, la Sección 5 los discute y la Sección 6 concluye.

---

## 2. Revisión de Literatura

### 2.1 El problema de horarios universitarios

El UCTP es un problema de scheduling combinatorio con restricciones de asignación de recursos. Ha sido ampliamente estudiado desde los años 60, pero conserva vigencia porque instancias reales continúan siendo intratables para métodos exactos sin límite de tiempo. Babaei, Karimpour y Hadidi (2015) presentan una taxonomía exhaustiva de enfoques y concluyen que ningún método domina universalmente: la efectividad depende de la estructura del problema, el tamaño de la instancia y las restricciones incorporadas.

La variante **CB-CTT** (Curriculum-Based Course Timetabling), formalizada en el International Timetabling Competition ITC-2007 [Di Gaspero, McCollum & Schaerf, 2007], es la más cercana al caso Javeriana: los conflictos entre asignaturas se derivan del currículo por semestre, no de restricciones individuales entre pares. El ITC-2019 [Müller, Rudová & Müllerová, 2025] extendió el benchmark con nuevas restricciones de distribución y disponibilidad. Ceschia, Di Gaspero y Schaerf (2023) proveen la revisión más reciente del estado del arte en educational timetabling.

### 2.2 Complejidad y necesidad de heurísticas

El UCTP es NP-hard [Babaei et al., 2015; Chen et al., 2021]. En la práctica, esto implica que el espacio de soluciones crece exponencialmente con el tamaño. Chen y colaboradores (2021) muestran que más del 50% de los trabajos publicados entre 2005 y 2020 recurren a metaheurísticas, mientras que los métodos exactos se usan principalmente como referencia o en instancias reducidas. Abdipoor et al. (2023) confirman esta tendencia en la revisión de metaheurísticas para UCTP del período 2015–2022.

### 2.3 Métodos exactos en timetabling

El uso de Gurobi para CB-CTT está respaldado por Rappos et al. (2022), quienes obtuvieron el segundo lugar en ITC-2019 con una formulación MIP resuelta con Gurobi bajo tiempo límite. Palma y Bornhardt (2020) presentan una formulación MILP multiobjetivo para CB-CTT con balance de secciones, conceptualmente cercana a la empleada aquí. Ambos trabajos reportan que los solvers exactos son competitivos en instancias pequeñas-medianas, pero su ventaja se erosiona rápidamente al escalar.

### 2.4 GRASP para scheduling

GRASP (Greedy Randomized Adaptive Search Procedure) fue introducido por Feo y Resende (1995) y formalizado para aplicaciones complejas por Resende y Ribeiro (2003). Su fortaleza en timetabling radica en la combinación de una fase constructiva guiada (que aprovecha la estructura del problema) con una fase de mejora local. Resende y Ribeiro (2003) también documentan que para problemas muy estructurados, valores bajos de α (cerca del greedy puro) tienden a dominar sobre valores altos.

### 2.5 Tabla resumen de referencias

| # | Referencia | Aporte principal |
|---|---|---|
| 1 | Feo & Resende (1995) | Definición canónica GRASP |
| 2 | Resende & Ribeiro (2003) | GRASP: técnicas de implementación y path-relinking |
| 3 | Di Gaspero et al. (2007) | Benchmark ITC-2007: CB-CTT |
| 4 | Babaei et al. (2015) | Survey UCTP: clasificación en 4 categorías de métodos |
| 5 | Bettinelli et al. (2015) | Survey CB-CTT: modelos exactos y heurísticos |
| 6 | Müller et al. (2025) | ITC-2019: benchmark 30 instancias reales y student sectioning |
| 7 | Palma & Bornhardt (2020) | MILP multiobjetivo CB-CTT con balance de secciones |
| 8 | Chen et al. (2021) | Survey: metaheurísticas son el enfoque más popular, seguido de híbridos |
| 9 | Rappos et al. (2022) | MIP + Gurobi: 2.º lugar ITC-2019 |
| 10 | Awad et al. (2022) | Tabu search adaptativo con lista dinámica; competitivo en benchmarks ITC2002 |
| 11 | Abdipoor et al. (2023) | Revisión metaheurísticas 2015–2022: 45 papers |
| 12 | Ceschia et al. (2023) | Revisión ETT: 6 formulaciones estándar, benchmarks y estado del arte |

---

## 3. Metodología

### 3.1 Datos e instancia

Los datos provienen de los planes de estudio de las 8 carreras de Ingeniería de la PUJ Bogotá disponibles en el Excel institucional, complementados con información verificada del sitio web de la universidad (edificios, laboratorios) y supuestos documentados donde la información no estaba disponible públicamente (capacidades de salones, software por asignatura).

**Estadísticas de la instancia completa:**

| Elemento | Valor |
|---|---|
| Carreras de Ingeniería | 8 |
| Semestres por carrera | 8 |
| Grupos por semestre | 2 |
| Secciones programables | 784 (3 THB excluidas, 0 créditos) |
| Bloques semanales requeridos | 2,198 |
| Salones disponibles | 71 (33 aulas · 20 salas cómputo · 18 labs) |
| Pares asignatura-salón compatibles | 8,975 |
| Franjas horarias disponibles/semana | 3,550 |
| Ocupación estimada | 61.9% |
| Estudiantes por grupo | mín 10 / máx 54 / promedio 24.8 |

Se definieron tres instancias para comparación progresiva: **piloto** (1 carrera — Bioingeniería, 98 secciones), **mediana** (4 carreras, 386 secciones) y **completa** (8 carreras, 784 secciones).

**Supuesto clave:** cada asignatura requiere tantos bloques de clase por semana como créditos tenga (1 crédito = 1 bloque de 1 hora). El horizonte de programación es lunes a viernes, períodos 1 a 10 (7:00–17:00).

### 3.2 Formulación matemática

**Conjuntos:** S (secciones, |S|=784), R (salones, |R|=71), D (días, |D|=5), P (períodos, |P|=10), G (grupos, |G|=128).

**Variable de decisión:**
```
x[s, r, d, p] ∈ {0,1}  =  1 si la sección s se asigna al salón r, día d, período p
```

**Restricciones duras (H1–H4):**

- **H1 — Completitud:** cada sección recibe exactamente b_s bloques semanales
- **H2 — No traslape de salón:** un salón alberga a lo sumo una clase por franja
- **H3 — No traslape de grupo:** un grupo no puede tener dos clases simultáneas
- **H4 — Compatibilidad:** solo se crean variables para pares (sección, salón) compatibles en tipo de espacio, software y capacidad

**Función objetivo — restricciones blandas (S1–S6, versión v4.1):**

```
min f(x) = 1·C_desp + 2·C_huecos + 3·C_exceso + 4·C_conc + 5·C_cont + 6·C_salon
```

| Componente | Descripción | Peso |
|---|---|---:|
| S1 — Desperdicio de capacidad | max(0, cap_r − est_s − 10) por bloque asignado | w1 = 1 |
| S2 — Huecos en el día del grupo | span del grupo en el día − clases del grupo | w2 = 2 |
| S3 — Exceso de carga diaria | max(0, clases_grupo_día − 6) | w3 = 3 |
| S4 — Concentración diaria | max(0, n_días_distintos_s − 1) por sección | w4 = 4 |
| S5 — Continuidad intra-clase | huecos internos entre bloques de la sección en el día | w5 = 5 |
| S6 — Estabilidad de salón | max(0, n_salones_distintos_{s,d} − 1) | w6 = 6 |

La jerarquía w6 > w5 > w4 > w3 > w2 > w1 refleja el impacto operativo: un cambio de salón en la misma jornada (S6) afecta más la operación que una asignatura en múltiples días (S4).

### 3.3 Métodos de solución

**Método exacto — Gurobi (MIP).** Se formula el problema con todas las restricciones duras y la función objetivo. Variables auxiliares modelan S2 (idle/before/after por grupo-día-período), S4 (y_dia[s,d] binario), S5 (idle_sec[s,d,p] por sección-día-período) y S6 (z_salon[s,r,d]). Límites de tiempo: 120 s (piloto), 300 s (mediana), 600 s (completa). Implementado en `etapa5_gurobi_v4_1.py`.

**Heurística constructiva — Greedy.** Ordena las secciones por score = b_s / |salones_compatibles_s| (más restringida primero). Para cada bloque evalúa todas las combinaciones (día, período, salón) y elige la de mínimo costo local incremental incluyendo los 6 componentes blandos. Prioriza días ya usados por la sección (S4 = 0 costo). Implementado en `etapa6_greedy_v4_1.py`.

**Metaheurística — GRASP.** Fase 1 (construcción): RCL (Restricted Candidate List) con parámetro α ∈ {0.1, 0.2, 0.3}; selección aleatoria entre candidatos con costo ≤ c_min + α·(c_max − c_min). Fase 2 (búsqueda local): movimientos de un bloque a otro slot, evaluación delta O(1) para ΔS1–ΔS6; máx 3 pasadas. Se repite hasta agotar el time limit. Implementado en `etapa7_grasp_v4_1.py`.

### 3.4 Plan experimental

| Método | Piloto (98 secc.) | Mediana (386 secc.) | Completa (784 secc.) |
|---|---|---|---|
| Gurobi | ✅ 120 s | ✅ 300 s | ✅ 600 s |
| Greedy | ✅ | ✅ | ✅ |
| GRASP α=0.1 | ✅ | — | ✅ |
| GRASP α=0.2 | — | — | ✅ |
| GRASP α=0.3 | ✅ | ✅ | ✅ |

Total: 11 ejecuciones. Las métricas de comparación son: valor f_obj, porcentaje de secciones asignadas, número de conflictos (H2+H3), gap MIP (Gurobi) y tiempo computacional.

---

## 4. Resultados

### 4.1 Tabla comparativa completa (v4.1)

| Instancia | Método | f_obj | S1 | S2 | S3 | S4 | S5 | S6 | Gap% | Tiempo | Factible |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Piloto | **GRASP α=0.1** | **486** | 438 | 0 | 0 | 48 | 0 | 0 | — | 120.4 s | ✅ |
| Piloto | Greedy | 521 | 420 | 0 | 33 | 68 | 0 | 0 | — | 0.22 s | ✅ |
| Piloto | GRASP α=0.3 | 535 | 449 | 10 | 3 | 68 | 5 | 0 | — | 122.5 s | ✅ |
| Piloto | Gurobi | 603 | 420 | 4 | 3 | 176 | 0 | 0 | 83.91% | 120.1 s | ✅ |
| Mediana | **Greedy** | **2,641** | 1,998 | 16 | 165 | 456 | 0 | 6 | — | 0.85 s | ✅ |
| Mediana | GRASP α=0.3 | 3,045 | 2,065 | 68 | 42 | 800 | 10 | 60 | — | 313.4 s | ✅ |
| Mediana | Gurobi | 3,587 | 2,002 | 400 | 87 | 1,024 | 20 | 54 | 92.19% | 300.2 s | ✅ |
| Completa | **Greedy** | **6,668** | 5,223 | 34 | 159 | 1,132 | 0 | 120 | — | 1.38 s | ✅ |
| Completa | GRASP α=0.1 | 8,774 | 5,059 | 290 | 45 | 3,120 | 50 | 210 | — | 608.3 s | ✅ |
| Completa | GRASP α=0.2 | 8,839 | 5,093 | 316 | 24 | 3,212 | 50 | 144 | — | 606.2 s | ✅ |
| Completa | GRASP α=0.3 | 8,902 | 5,087 | 338 | 24 | 3,228 | 45 | 180 | — | 627.5 s | ✅ |
| Completa | Gurobi | **No factible** | — | — | — | — | — | — | — | 600.4 s | ❌ |

*Nota: todos los valores f_obj verificados algebraicamente. Todos los runs factibles reportan pct_asignadas=100%, n_conflictos_salon=0, n_conflictos_grupo=0.*

### 4.2 Análisis por instancia

**Piloto:** GRASP α=0.1 obtiene el mejor f_obj (486), superando al Greedy en 6.7% y a Gurobi en 19.4%. Gurobi termina por límite de tiempo con un gap del 83.91%, lejos de la optimalidad. Todos los métodos logran S5=0 y S6=0.

**Mediana:** Greedy obtiene el mejor resultado (2,641), 13.3% mejor que GRASP α=0.3 y 26.3% mejor que Gurobi. El gap de Gurobi sube al 92.19%, evidenciando la dificultad del modelo MIP con las restricciones blandas S5 y S6.

**Completa:** Greedy gana con f_obj=6,668 en 1.38 segundos. Gurobi no encuentra solución factible en 600 segundos: S5 y S6 agregan más de 120,000 variables binarias adicionales, haciendo el árbol de Branch & Bound inmanejable. La diferencia entre Greedy y GRASP es de 31.5%, principalmente explicada por c_conc_raw (283 vs 780).

### 4.3 Desempeño por componente — instancia completa

| Método | f_obj | S1 desp | S2 huecos | S3 exceso | S4 conc | S5 cont | S6 salón |
|---|---|---|---|---|---|---|---|
| **Greedy** | **6,668** | 5,223 | **34** | 159 | **1,132** | **0** | 120 |
| GRASP α=0.1 | 8,774 | **5,059** | 290 | **45** | 3,120 | 50 | 210 |
| GRASP α=0.2 | 8,839 | 5,093 | 316 | 24 | 3,212 | 50 | 144 |
| GRASP α=0.3 | 8,902 | 5,087 | 338 | 24 | 3,228 | 45 | 180 |

### 4.4 Verificación de hipótesis

| Hipótesis | Resultado |
|---|---|
| Gurobi resuelve piloto a optimalidad | ❌ TIME_LIMIT, gap=83.91% (S5+S6 aumentan la complejidad) |
| Gurobi no resuelve completa a optimalidad | ✅ Sin solución factible en 600 s |
| GRASP supera a Greedy en todas las instancias | ⚠️ Parcial: solo en piloto (−6.7%) |
| w4=4 concentra bloques en 1 día | ✅ Greedy: 80–92% secciones en 1 día |
| N_MAX_DIA=6 es compatible con S4 | ✅ c_exceso bajo en todos los métodos factibles |

---

## 5. Discusión

### 5.1 ¿Por qué el Greedy supera a GRASP en instancias grandes?

El resultado no es trivial y tiene tres causas cuantificables:

**Primera causa — Pocas iteraciones.** S5 y S6 encarecen cada iteración de GRASP. En v3 (sin S5/S6) se completaban ~100 iteraciones; en v4.1 se completaron 15 en mediana y 18–57 en completa. Con pocas iteraciones, la búsqueda local tiene capacidad exploratoria limitada.

**Segunda causa — La aleatoriedad daña el componente más pesado.** El componente dominante en instancias grandes es S4 (concentración diaria). En completa, c_conc_raw del Greedy es 283 vs 780 del mejor GRASP. La diferencia ponderada es 1,988 puntos (×4). La aleatoriedad de la RCL dispersa bloques en más días, y el peso w4=4 castiga esa dispersión fuertemente. GRASP pierde lo que gana en S1 (−164) y mucho más en S4 (+1,988).

**Tercera causa — Búsqueda local insuficiente para reparar S4.** Reducir c_conc_raw de 780 a 283 requeriría mover simultáneamente múltiples bloques de una sección entre días. Movimientos de un bloque a la vez (búsqueda local actual) no tienen ese poder de reorganización. Resende y Ribeiro (2003) anticipan esto: en problemas muy estructurados, α pequeño (casi greedy puro) domina, y aquí incluso α=0.1 no es suficiente.

### 5.2 ¿Por qué el Greedy supera a Gurobi bajo time limit?

En teoría, Gurobi encuentra el óptimo dado tiempo suficiente. Bajo time limit con gap >80%, la solución incumbente es de baja calidad. S5 y S6 añaden variables auxiliares (idle_sec[s,d,p], z_salon[s,r,d]) que incrementan la complejidad del modelo en ~20–25% y dilatan el árbol B&B. Este resultado es consistente con lo observado por Rappos et al. (2022), quienes reportan que instancias grandes del ITC-2019 requieren estrategias iterativas de reducción de variables para que el solver MIP sea competitivo.

### 5.3 S5 = 0 siempre, S6 > 0 en instancias grandes

S5 (continuidad intra-clase) es una restricción **local**: el greedy solo necesita encontrar un período adyacente libre para el grupo. Como el grupo se construye progresivamente, los períodos adyacentes suelen estar disponibles. S6 (estabilidad de salón) es una restricción **global**: requiere que el mismo salón específico esté libre en otro período del mismo día, compitiendo con todos los grupos del horario. A medida que el horario se llena, la probabilidad de reusar el mismo salón disminuye. Que S5=0 y S6>0 refleja la diferente dificultad estructural, no un fallo del algoritmo.

### 5.4 Implicación práctica

Para una coordinación académica real con tiempo limitado, el Greedy provee una solución de alta calidad casi instantáneamente (1.38 s para 784 secciones). GRASP añade valor solo en instancias pequeñas. Gurobi sirve como referencia formal y diagnóstico de factibilidad. La conclusión no es que un método sea universalmente superior, sino que la efectividad depende del tamaño de la instancia, las restricciones incorporadas y el presupuesto computacional disponible.

---

## 6. Conclusiones

Este trabajo comparó tres enfoques para el problema de scheduling académico de las carreras de Ingeniería de la PUJ con una función objetivo de seis criterios de calidad. Los principales hallazgos son:

1. **El Greedy es el método más robusto en instancias medianas y completas.** Obtiene el mejor f_obj disponible en 2 de 3 instancias con tiempos inferiores a 2 segundos. Su construcción determinística favorece naturalmente la concentración (S4) y la continuidad (S5=0 en todos los casos).

2. **GRASP supera al Greedy solo en la instancia piloto (−6.7%).** En instancias grandes, la aleatoriedad deteriora S4 más de lo que GRASP recupera en S1. El parámetro α=0.1 (casi greedy puro) domina consistentemente.

3. **El modelo exacto pierde escalabilidad al incorporar restricciones realistas.** S5 y S6 transforman un problema que Gurobi resolvía óptimamente en piloto (v3: f_obj=420, gap=0%) en uno que no encuentra solución factible en completa bajo v4.1.

4. **El diseño de la función objetivo determina el desempeño relativo de los algoritmos.** Con w6>w5>w4, la estructura del problema (concentración diaria, continuidad, estabilidad de salón) se vuelve muy rígida, beneficiando al método determinístico.

**Limitaciones:** no se incorporaron profesores como restricción; las capacidades de salón y software por asignatura se estimaron donde no había información oficial; la búsqueda local de GRASP usa solo movimientos de un bloque a la vez.

**Trabajo futuro:** warm start de Gurobi desde la solución Greedy; búsqueda local de GRASP orientada específicamente a reducir c_conc; reformulación por patrones (asignar sesiones completas consecutivas en lugar de bloques individuales); incorporación de disponibilidad docente.

---

## Referencias


1. Feo, T.A. & Resende, M.G.C. (1995). Greedy Randomized Adaptive Search Procedures. *Journal of Global Optimization*, 6(2), 109–133.
   
2. Resende, M.G.C. & Ribeiro, C.C. (2003). Greedy Randomized Adaptive Search Procedures. En Glover & Kochenberger (Eds.), *Handbook of Metaheuristics*, Springer, pp. 219–249.
   
3. Di Gaspero, L., McCollum, B. & Schaerf, A. (2007). The Second International Timetabling Competition (ITC-2007): CB-CTT (Track 3). *PATAT*.
   
4. Babaei, H., Karimpour, J. & Hadidi, A. (2015). A survey of approaches for university course timetabling problem. *Computers & Industrial Engineering*, 86, 43–59.
   
5. Bettinelli, A., Cacchiani, V., Roberti, R. & Toth, P. (2015). An overview of curriculum-based course timetabling. *TOP*, 23(2), 313–349. DOI: 10.1007/s11750-015-0366-z
   
6. Müller, T., Rudová, H. & Müllerová, Z. (2025). Real-world university course timetabling at the International Timetabling Competition 2019. *Journal of Scheduling*, 28(2), 247–267. DOI: 10.1007/s10951-023-00801-w
   
7. Palma, C.D. & Bornhardt, P. (2020). Section Balance in CB-CTT Integer Optimization. *Mathematics*, 8(10), 1763.
   
8. Chen, M.C., Sze, S.N., Goh, S.L., Sabar, N.R. & Kendall, G. (2021). A Survey of University Course Timetabling Problem: Perspectives, Trends and Opportunities. *IEEE Access*, 9, 106515–106529. DOI: 10.1109/ACCESS.2021.3100613
   
9.  Rappos, E., Thiémard, E., Robert, S. & Hêche, J.F. (2022). A mixed-integer programming approach for solving university course timetabling problems. *Journal of Scheduling*, 25, 391–404. DOI: 10.1007/s10951-021-00715-5
    
10. Awad, F.H., Al-Kubaisi, A. & Mahmood, M. (2022). Large-scale timetabling with adaptive tabu search. *Journal of Intelligent Systems*, 31(1), 168–176.
    
11. Abdipoor, S., Yaakob, R., Goh, S.L. & Abdullah, S. (2023). Meta-heuristic approaches for the University Course Timetabling Problem. *Intelligent Systems with Applications*, 19, 200253. DOI: 10.1016/j.iswa.2023.200253
    
12. Ceschia, S., Di Gaspero, L. & Schaerf, A. (2023). Educational Timetabling: Problems, Benchmarks, and State-of-the-Art Results. *European Journal of Operational Research*, 308(1), 1–18. DOI: 10.1016/j.ejor.2022.07.011
