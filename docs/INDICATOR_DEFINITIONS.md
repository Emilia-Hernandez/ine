# Definiciones de indicadores

Las páginas 17–18 del manual oficial prevalecen sobre la fórmula provisional anterior del plan maestro. Los TXT incluidos en los ZIP usan los campos `LN`, `SV`, `NV` y `NS` en los seis años y concilian exactamente por fila.

| Indicador o variable | Definición y fórmula | Unidad / denominador | Referencia | Campos 2009–2024 | Discrepancia y decisión |
|---|---|---|---|---|---|
| Lista nominal | Personas registradas en los cuadernillos de todas las casillas catalogadas. | conteo | Manual p. 17; TXT de cada ZIP | `LN` en todos | No incluye casillas especiales ni residentes en el extranjero según TXT. |
| Sí votaron | Registros con marca de voto. | conteo | Manual p. 17; TXT | `SV` en todos | No equivale a votos partidistas ni a actas de cómputo. |
| No votaron | Registros sin marca de voto. | conteo | Manual pp. 17–18; TXT | `NV` en todos | Es el numerador de abstención identificada. |
| Registros con participación identificada | `SV + NV`. | conteo | Derivado de manual pp. 17–18 | derivado en todos | Denominador oficial de participación/abstención. |
| Registros no especificados | Registros sin información clara por cuadernillo sin marcas/no disponible/página no disponible; los TXT 2009–2021 añaden cuadernillo solicitado por autoridad jurisdiccional. | conteo | Manual p. 18; TXT | `NS` en todos | No son abstención ni votos nulos. Se conserva la diferencia textual entre versiones. |
| Participación oficial del tablero | `SV / (SV + NV)`. | proporción o % de registros identificados | Manual p. 17 | derivada de `SV`, `NV` | Si el denominador es cero: no definida. Agregar conteos antes de dividir. |
| Abstención oficial del tablero | `NV / (SV + NV)`. | proporción o % de registros identificados | Manual p. 18 | derivada de `SV`, `NV` | `NS` queda fuera del numerador y denominador. |
| Proporción no especificada | `NS / LN`. | proporción o % de lista nominal | Manual p. 18 | derivada de `NS`, `LN` | Si `LN=0`: no definida. |
| Cobertura identificada | `(SV + NV) / LN`. | proporción de lista nominal | derivación auditiva | derivada en todos | Se reporta para entender cuánto de LN tiene participación identificada. |
| Sensibilidad: sí votaron sobre LN | `SV / LN`. | proporción de lista nominal | indicador adicional del proyecto | derivada en todos | No se etiqueta como participación oficial. |

Resultados agregados nacionales, calculados como razón de sumas:

| Año | Participación oficial | Abstención oficial | NS / LN | Cobertura identificada | SV / LN (sensibilidad) |
|---:|---:|---:|---:|---:|---:|
| 2009 | 44.0608% | 55.9392% | 2.4082% | 97.5918% | 42.9997% |
| 2012 | 62.0830% | 37.9170% | 0.2205% | 99.7795% | 61.9461% |
| 2015 | 47.0736% | 52.9264% | 6.1259% | 93.8741% | 44.1899% |
| 2018 | 62.3651% | 37.6349% | 6.8329% | 93.1671% | 58.1038% |
| 2021 | 51.8380% | 48.1620% | 4.3229% | 95.6771% | 49.5971% |
| 2024 | 59.6700% | 40.3300% | 6.4331% | 93.5669% | 55.8314% |

Estas cifras describen los archivos descargados y su universo de cuadernillos; no se compararon todavía con cifras filtradas del dashboard ni se interpretan como panel territorial armonizado.
