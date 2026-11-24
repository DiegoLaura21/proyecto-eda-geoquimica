# Guía de EDA geoquímico y limpieza trazable

Esta guía parte de los certificados y termina en una tabla de trabajo con decisiones documentadas. Puedes recorrerla con el Proyecto Quebrada Brújula y repetirla después con tus propios datos. El caso contiene muestras sintéticas de roca. Mantén por separado sedimentos, suelos, chips, testigos u otros soportes cuando las poblaciones o sus métodos analíticos sean distintos.

## 1. Completa el contexto antes de calcular

1. Guarda una copia de los certificados originales, los registros de muestreo y el listado de envíos. Identifica el responsable y la versión de cada archivo que entra a una corrida.
2. Cruza geología y ensayes por un ID único. Revisa que el medio, el dominio, el lote analítico, las unidades, el método y los límites correspondan al certificado correcto. Si una muestra tiene dos métodos o varios ensayes, define quién decide el valor oficial y registra las alternativas aparte.
3. En sondajes, comprueba intervalos, profundidades, coordenadas y solapes antes de unirlos con el análisis. En muestreo de superficie, verifica sistema de coordenadas, ubicaciones y representatividad. Cuando compares dominios o prepares un mapa de campaña, toma en cuenta la densidad y el soporte del muestreo.
4. Identifica cambios de digestión, acabado, alícuota, laboratorio o rango analítico. Empieza con grupos comparables. El programa permite combinar campos de agrupación, por ejemplo `["medio", "dominio", "metodo"]` si todos están presentes. Mantén el detalle de blancos, materiales certificados y duplicados por lote. [CIM, buenas prácticas de exploración mineral](https://mrmr.cim.org/en/practice-guidelines/exploration/).

## 2. Instala y corre el ejemplo

Abre la terminal en la raíz de este proyecto y usa Python 3.11 o posterior.

**Windows PowerShell**

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe src/ejecutar_eda.py
```

**macOS o Linux**

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python src/ejecutar_eda.py
```

El ejemplo lee las 1.000 muestras de `datos/`, aplica el QA/QC sintético y escribe en `resultados/`. Para las siguientes instrucciones se muestra `python` como abreviatura del Python del entorno virtual.

## 3. Prepara tu CSV de muestras

Usa CSV UTF-8 con campos separados por coma, encabezados únicos y punto decimal. Cada fila representa una muestra primaria. Guarda los duplicados de control en otro archivo. Ejemplo de columnas para una configuración reducida de tres analitos.

```csv
muestra_id,lote,dominio,medio,x_local_m,y_local_m,Au_ppb,As_ppm,Fe_pct
M-001,L01,Veta,roca,114.5,521.2,<5,18.2,3.70
M-002,L01,Veta,roca,121.0,524.6,1250,67,4.18
M-003,L02,Hospedante,roca,210.8,498.7,>10000,ND,2.55
```

La tabla de arriba solo ilustra el formato. Para ejecutarla configura esos tres elementos y sus columnas. Con tres filas se generará el inventario de estados, pero cada grupo tendrá datos insuficientes para el MAD. Puedes agregar metadatos al CSV. El programa conserva esas columnas en la salida ancha.

| Valor original | Interpretación | Uso en el código |
| --- | --- | --- |
| `1250` en `Au_ppb` | Concentración cuantificada | Se normaliza a 1,25 ppm en el ejemplo. |
| `<5` en `Au_ppb` | Censura izquierda y límite de reporte de 5 ppb | El límite se conserva como 0,005 ppm. El valor cuantificado queda vacío. |
| `>10000` en `Au_ppb` | Censura derecha, por encima del rango reportado | Se conserva el límite de 10 ppm y se marca para revisar un reensaye por sobrelímite. |
| `ND` o `BDL` | Resultado bajo límite, si el certificado define un límite aplicable | Usa el límite de la configuración. Con `null`, queda pendiente con estado `nd_sin_limite`. |
| Celda vacía, `NA`, `N/A`, `NULL` o `SIN ENSAYO` | Falta un resultado | Se cuenta como faltante. |
| `0`, `-9` u otro texto | Señal por verificar | Se conserva el dato de origen. Comprueba convenciones de códigos en el certificado antes de corregirlo. |

El script usa **LR** como límite de reporte para el dato calificado. Comprueba si tu laboratorio distingue límite de detección, cuantificación y reporte. Si el LR cambia por muestra, método o lote, usa calificadores explícitos como `<5` y `<10`. Para un `ND` sin LR confirmado, usa `null`. Los histogramas, cuantiles y correlaciones del proyecto describen **solo resultados cuantificados**. Si necesitas inferir la distribución completa bajo censura, evalúa métodos como ROS o máxima verosimilitud con un especialista, considerando el tipo de censura, la proporción y los límites múltiples. [USGS, resultados geoquímicos censurados](https://www.usgs.gov/publications/objective-replacement-method-censored-geochemical-data).

Para concentraciones másicas, **1 ppm = 1 mg/kg = 1 g/t**, **1.000 ppb = 1 ppm** y **1 % = 10.000 ppm**. Configura una unidad de entrada por columna. Si un certificado cambia de unidad entre resultados, armoniza por método con trazabilidad antes de combinarlo. Comprueba también que la base seca o húmeda coincida. Una conversión de escala solo cambia las unidades.

## 4. Adapta la configuración

Copia [configuracion.json](../datos/configuracion.json) a `datos/mi_config.json`. Cambia lo necesario.

| Campo | Qué ingresar |
| --- | --- |
| `proyecto` | Nombre del análisis. |
| `columna_id`, `columna_lote` | Encabezados reales del ID único y del lote. |
| `grupos` | Campos para construir poblaciones comparables. `[]` usa una población única. |
| `columnas_coordenadas` | Dos columnas numéricas X e Y de una proyección común. Usa `null` si careces de coordenadas. El programa las grafica tal como se reciben. |
| `elementos` | Un bloque por analito. Para cada uno indica `columna`, `unidad_entrada`, `unidad_salida` y `limite_reporte` en **unidad de entrada**. Usa el símbolo `Au` para activar el panel especial de oro. |
| `muestra_min_detecciones` | Mínimo de cuantificados para el MAD por elemento y grupo. También es el mínimo de pares para reportar una correlación. El ejemplo usa 25. |
| `fraccion_min_detectados` | Fracción mínima de cuantificados para el MAD. El ejemplo usa 0,5. |
| `umbral_mad` | Umbral absoluto del puntaje robusto. El ejemplo usa 3,5 para priorizar revisión. |
| `qaqc` | Reglas de blancaje y precisión. Adapta los multiplicadores y límites a tu protocolo documentado. |

## 5. Adjunta y revisa QA/QC

El [archivo sintético de controles](../datos/controles_sinteticos.csv) sirve de plantilla. En tu archivo usa una fila por control y elemento, identificada por `control_id` y `elemento`. Todos los resultados y límites de esta tabla deben venir en la **unidad de salida** del elemento. El LR explícito tiene prioridad. Cuando falta, se usa el LR de la configuración convertido a esa unidad.

| Tipo | Campos adicionales | Qué revisa |
| --- | --- | --- |
| `blanco` | `resultado` y `limite_reporte` cuando varía | Alerta si un valor cuantificado supera el múltiplo del LR configurado. Revísalo con el tipo de blanco, la secuencia y el criterio del programa de muestreo. |
| `crm` | `resultado`, `referencia` y `tolerancia` absoluta | Compara con el intervalo de aceptación definido para el material de referencia certificado. Usa el certificado y el protocolo correspondiente. |
| `duplicado_campo`, `duplicado_rechazo`, `duplicado_pulpa` | `muestra_id` del primario en el mismo lote, `resultado` y, si corresponde, `limite_reporte` | Compara con el primario cuando ambos cuantifican por encima o igual al múltiplo elegido del LR común del par. Si sus límites difieren, usa el mayor aplicable al par. |

El RPD es **100 × |A − B| / [(A + B)/2]**. Cerca del LR puede amplificar diferencias pequeñas. La herramienta deja esos pares como `revisar` y no calcula RPD. Los criterios de ejemplo (blanco hasta **5× LR**, RPD hasta **30 %** y ambos resultados desde **10× LR**) son decisiones de simulación. El control de blancos y CRM se asocia al **lote y elemento**. El duplicado se asocia con el **primario y elemento**. Revisa los controles individuales para conocer la cobertura de cada tipo. `sin_control` indica que ese alcance carece de control cargado. Un resultado `ok` indica que los controles evaluados dentro de ese alcance pasaron las reglas implementadas. [CIM, buenas prácticas de exploración mineral](https://mrmr.cim.org/en/practice-guidelines/exploration/).

## 6. Ejecuta el EDA y examina las señales

```bash
python src/ejecutar_eda.py --muestras datos/mi_campana.csv --config datos/mi_config.json --qaqc datos/mis_controles.csv --salida resultados/mi_campana_base
```

Si aún no tienes QA/QC compatible, omite `--qaqc`. Cuando especificas `--muestras`, los controles sintéticos no intervienen. Mantén una carpeta por corrida para evitar confundir versiones del plan de revisión.

1. Abre `resumen_elemento_grupo.csv`. Empieza por cobertura, censura, faltantes y tamaños de muestra. Revisa el % cuantificado por dominio y método antes de comparar medianas o percentiles.
2. Lee los histogramas en log₁₀ junto con la gráfica de calidad. Separar log₁₀ de los valores positivos ayuda a inspeccionar colas asimétricas. Resuelve errores estructurales y revisa si un histograma mezcla medios, litologías o métodos.
3. Abre `modelos_mad.csv`. El puntaje es `0.67448975 × [log10(x) − mediana(log10(x))] / MAD(log10(x))`. El MAD es la mediana de las desviaciones absolutas respecto a la mediana. El programa marca extremos altos y bajos por elemento y grupo. Si faltan detecciones o el MAD es prácticamente cero, informa ese motivo. En estos casos conviene revisar el grupo, el redondeo y los límites antes de intentar otra regla. El umbral es de exploración estadística y su interpretación depende de la distribución y del dominio. [NIST, detección de valores atípicos](https://www.itl.nist.gov/div898/handbook/eda/section3/eda35h.htm).
4. Inspecciona `correlacion_spearman.csv` junto con `correlacion_n_pares.csv`. Cada par usa las muestras con ambos valores cuantificados. El resultado global puede reflejar mezcla de geologías, efectos de censura o un tamaño de muestra distinto en cada par. Corre por dominios comparables si quieres contrastar asociaciones. Cuando trabajes con composiciones de suma cerrada, considera métodos de razones logarítmicas adecuados y un tratamiento previo de censuras.
5. Cruza `cola_revision.csv` con certificados, blancos, CRM, duplicados, geología y ubicación. Un valor alto acompañado por otros elementos puede ser un objetivo geológico. Una señal aislada puede ser mineralización real, un sobrelímite, contaminación o un error de registro. Documenta qué evidencia diferencia esas posibilidades. Los faltantes se informan por separado.

## 7. Oro y efecto pepita

Los granos gruesos, raros o agrupados pueden repartir el Au de manera desigual al tomar una muestra o dividirla en alícuotas. Dos ensayes del mismo material pueden diferir mucho. En geostatística, el efecto pepita del variograma recoge variación a distancias menores al soporte observado y contribuciones del error de muestreo o medición. Una cola larga, un valor extremo o un RPD alto por sí solos no permiten atribuirlo al oro grueso. [Dominy y colaboradores, caracterización de partículas de oro y optimización del muestreo](https://www.mdpi.com/2075-163X/11/10/1109).

1. **Verifica el certificado.** Confirma ID, unidad, alícuota, preparación, método, LR y sobrelímite. Para `>x`, solicita el resultado por el método de rango alto si el protocolo lo contempla.
2. **Ubica el valor en su dominio.** Busca vetas, alteración, oro visible, muestreo de contacto y continuidad de datos cercanos. Una baja correlación de Au con As o Sb no invalida una muestra de oro. No mezcles soportes distintos solo para aumentar el tamaño del grupo.
3. **Compara duplicados por etapa.** Los duplicados de campo incorporan variabilidad de toma y etapas posteriores, los de rechazo informan sobre el submuestreo de material triturado y etapas posteriores, y los de pulpa ayudan a evaluar el submuestreo fino y el ensayo. Compara rangos de ley y suficientes pares equivalentes. Diferencias de dispersión pueden orientar la investigación, pero no atribuyen por sí solas una causa única.
4. **Evalúa el siguiente ensayo con el laboratorio.** Según geología y material retenido, considera reensayos de pulpa, nuevos splits de rechazo, mayor masa de muestra o de alícuota, y ensayo al fuego con tamizado metálico (`screen fire assay`) cuando el estudio de oro grueso lo justifique. Un reensaye de pulpa puede repetirse bien aunque la reducción de masa anterior haya introducido variabilidad. [Dominy y colaboradores, muestreo y ensayo de oro grueso](https://journals.sagepub.com/doi/10.1179/aes.2000.109.3.145).
5. **Mide la influencia de la cola.** Usa el [panel de Au](../resultados/figuras/04_oro.png) y `sensibilidad_oro.csv`. Compara mediana, media y cuánto cambia la media al omitir temporalmente el 1 % superior de los **cuantificados** por dominio, redondeado hacia arriba a muestras enteras. La suma de concentraciones se usa para mostrar influencia estadística. El cálculo carece de ponderación por masa o soporte y no estima metal ni recursos.
6. **Separa limpieza de estimación.** Conserva valores altos respaldados. El análisis de sensibilidad no modifica la tabla de trabajo. Si posteriormente estudias un recorte de leyes (`top cut`), documéntalo como decisión de estimación por dominio, con validación geológica y espacial, y conserva la serie original.

En el caso de práctica hay dos valores altos de Au en el dominio intrusivo. `QB-0128` ingresó como **125.000 ppb** y el certificado simulado respalda **1.250 ppb**, equivalentes a 1,25 ppm. `QB-0500` registra **14.800 ppb**, equivalentes a 14,8 ppm, y se conserva con la evidencia simulada. El criterio estadístico detecta ambos. La diferencia entre las decisiones viene de verificar el dato.

## 8. Registra las decisiones y regenera la tabla

Copia `decisiones_plantilla.csv` a tu carpeta de trabajo. Mantén `muestra_id`, `elemento` y `valor_original` con el texto exacto que figura en la plantilla. Completa `accion`, `evidencia` y, para corregir, `valor_corregido`. Incluye fecha, responsable y referencia del certificado o reensaye en la evidencia o en el registro de revisión asociado.

| Acción | Cuándo usarla |
| --- | --- |
| `conservar` | Hay sustento para el resultado original, aun si quedó marcado. |
| `corregir` | Existe un valor oficial comprobable. Ingresa un valor positivo o un límite explícito en unidad de **salida**. |
| `excluir` | El resultado carece de respaldo utilizable o corresponde a un error confirmado sin reemplazo. Se excluye ese analito de la vista derivada y se conserva en el registro original. |
| Acción vacía | Sigue pendiente. La vista de trabajo mantiene los valores positivos sin decisión y su estado queda en el detalle auditable. |

Para practicar con [decisiones_ejemplo.csv](../datos/decisiones_ejemplo.csv), usa el caso incluido.

```bash
python src/ejecutar_eda.py --decisiones datos/decisiones_ejemplo.csv --salida resultados/ejemplo_revisado
```

El ejercicio aplica tres decisiones y deja 330 combinaciones pendientes. En el dominio intrusivo, la fracción de la suma de concentraciones de Au atribuida a la cola superior cambia de 96,9 % a 78,1 %. La cola sigue pesando aun después de corregir el error de transcripción.

Para tu campaña, vuelve a pasar las mismas muestras, configuración y controles de la primera corrida. Añade `--decisiones datos/mis_decisiones.csv` y cambia `--salida` a una carpeta de versión nueva. El script comprueba la correspondencia con el valor original y guarda una huella SHA-256 de las entradas. Las señales MAD y QA/QC corresponden a la corrida sobre los ensayes originales. Las estadísticas y las gráficas usan los estados de trabajo tras las decisiones. Una revisión nueva del certificado puede requerir actualizar tanto la entrada oficial como sus controles y generar otra línea base.

## 9. Elige qué archivo entregar

| Salida | Contenido y uso |
| --- | --- |
| `resumen.json` | Tamaño de la corrida, estados, candidatos, decisiones y huellas de los archivos. |
| `analitos_auditados.csv` | Una fila por muestra y elemento, con original literal, unidad normalizada, límites, señales, resultado de uso y evidencia. |
| `cola_revision.csv`, `decisiones_plantilla.csv` | Motivos de revisión históricos y plantilla con casos aún pendientes. |
| `concentraciones_uso.csv` | Tabla ancha con metadatos, concentraciones en unidades de salida y censuras conservadas como texto `<` o `>`. Los inválidos, faltantes y excluidos quedan vacíos. Usa el detalle auditable para distinguirlos. |
| `resumen_elemento_grupo.csv`, `modelos_mad.csv` | Cuantiles de detectados, cobertura, conteos y parámetros de la regla robusta. |
| `correlacion_spearman.csv`, `correlacion_n_pares.csv` | Matriz de correlaciones global y tamaños por par. |
| `qaqc_detalle.csv`, `precision_duplicados.csv` | Resultado por control y resumen de duplicados por etapa con número de RPD evaluables. |
| `sensibilidad_oro.csv`, `figuras/` | Efecto estadístico de la cola alta y gráficos para documentar el diagnóstico. |

Antes de entregar la base de trabajo, concilia el número de muestras con el original, valida las unidades, identifica qué lotes se liberaron según el protocolo, registra las decisiones pendientes y conserva la corrida que sustenta lo que publicas o compartes.

