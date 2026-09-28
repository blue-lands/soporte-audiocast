"""Las 71 tiendas oficiales de Tottus.

Fuente: `frontend/src/data/tottus-stores.ts` de MediaFlow (capturado de tottus.cl el 2026-08-18), copiado de la tabla de
`soporte-audiocast-central-y-tiendas.md` §6. No se agregan ni se quitan tiendas.

Única diferencia con la fuente: Machalí, Rancagua Centro, Rengo, San Fernando y San Vicente venían bajo "Región de
Valparaíso" y aquí van en "Región de O'Higgins", que es donde están. Importa porque la región decide con qué caja
simulada se asocia cada tienda (app/directorio.py).
"""

# (id, nombre, comuna, región, alias)
# alias: solo lo que la búsqueda no resuelve sola (palabras pegadas, nombres de uso común); separadas por '|'.
TIENDAS = [
    ("nataniel-cox", "Nataniel Cox", "Santiago Centro", "Región Metropolitana", ""),
    ("recoleta", "Recoleta", "Recoleta", "Región Metropolitana", ""),
    ("la-cisterna", "La Cisterna", "La Cisterna", "Región Metropolitana", ""),
    ("alameda", "Alameda", "Estación Central", "Región Metropolitana", ""),
    ("buin", "Buín", "Buin", "Región Metropolitana", ""),
    ("catedral", "Catedral", "Santiago Centro", "Región Metropolitana", ""),
    ("ciudad-empresarial", "Ciudad Empresarial", "Huechuraba", "Región Metropolitana", ""),
    ("colina", "Colina", "Colina", "Región Metropolitana", ""),
    ("colina-chamisero", "Colina Chamisero", "Colina", "Región Metropolitana", ""),
    ("el-bosque", "El Bosque", "El Bosque", "Región Metropolitana", ""),
    ("el-monte", "El Monte", "El Monte", "Región Metropolitana", ""),
    ("providencia", "Providencia", "Providencia", "Región Metropolitana", ""),
    ("huechuraba", "Huechuraba", "Huechuraba", "Región Metropolitana", ""),
    ("las-condes", "Las Condes", "Las Condes", "Región Metropolitana", ""),
    ("la-florida", "La Florida", "La Florida", "Región Metropolitana", ""),
    ("los-dominicos", "Los Dominicos", "Las Condes", "Región Metropolitana", ""),
    ("maipu", "Maipú", "Maipú", "Región Metropolitana", ""),
    ("mall-plaza-tobalaba", "Mall Plaza Tobalaba", "Puente Alto", "Región Metropolitana", ""),
    ("melipilla", "Melipilla", "Melipilla", "Región Metropolitana", ""),
    ("padre-hurtado", "Padre Hurtado", "Padre Hurtado", "Región Metropolitana", ""),
    ("penaflor", "Peñaflor", "Peñaflor", "Región Metropolitana", ""),
    ("piedra-roja", "Piedra Roja", "Colina", "Región Metropolitana", ""),
    ("plaza-egana", "Plaza Egaña", "Ñuñoa", "Región Metropolitana", ""),
    ("plaza-oeste", "Plaza Oeste", "Cerrillos", "Región Metropolitana", ""),
    ("puente-alto", "Puente Alto", "Puente Alto", "Región Metropolitana", ""),
    ("quilicura", "Quilicura", "Quilicura", "Región Metropolitana", ""),
    ("quilin", "Quilín", "Peñalolén", "Región Metropolitana", ""),
    ("san-bernardo-estacion", "San Bernardo Estación", "San Bernardo", "Región Metropolitana", ""),
    ("san-bernardo-plaza", "San Bernardo Plaza", "San Bernardo", "Región Metropolitana", ""),
    ("talagante-cordillera", "Talagante Cordillera", "Talagante", "Región Metropolitana", ""),
    ("talagante-plaza", "Talagante Plaza", "Talagante", "Región Metropolitana", ""),
    ("vicuna-mackenna", "Vicuña Mackenna", "Santiago Centro", "Región Metropolitana", ""),
    ("vitacura", "Vitacura", "Vitacura", "Región Metropolitana", ""),
    ("vivaceta", "Vivaceta", "Independencia", "Región Metropolitana", ""),
    ("walker-martinez", "Walker Martínez", "La Florida", "Región Metropolitana", ""),
    ("quillayes", "Quillayes", "La Florida", "Región Metropolitana", ""),
    ("antofagasta-norte", "Antofagasta Norte", "Antofagasta", "Región de Antofagasta", ""),
    ("antofagasta-centro", "Antofagasta Centro", "Antofagasta", "Región de Antofagasta", ""),
    ("antofagasta-mall", "Antofagasta Mall", "Antofagasta", "Región de Antofagasta", ""),
    ("calama-centro", "Calama Centro", "Calama", "Región de Antofagasta", ""),
    ("copiapo-los-carrera", "Copiapó Los Carrera", "Copiapó", "Región de Atacama", ""),
    ("mall-plaza-copiapo", "Mall Plaza Copiapó", "Copiapó", "Región de Atacama", ""),
    ("vallenar", "Vallenar", "Vallenar", "Región de Atacama", ""),
    ("coquimbo", "Coquimbo", "Coquimbo", "Región de Coquimbo", ""),
    ("ovalle", "Ovalle", "Ovalle", "Región de Coquimbo", ""),
    ("mall-plaza-la-serena", "Mall Plaza La Serena", "La Serena", "Región de Coquimbo", ""),
    ("balmaceda", "Balmaceda", "La Serena", "Región de Coquimbo", ""),
    ("concon", "Concón", "Concón", "Región de Valparaíso", ""),
    ("curauma", "Curauma", "Valparaíso", "Región de Valparaíso", ""),
    ("valparaiso", "Valparaíso", "Valparaíso", "Región de Valparaíso", ""),
    ("la-calera", "La Calera", "La Calera", "Región de Valparaíso", ""),
    ("maitencillo", "Maitencillo", "Puchuncaví", "Región de Valparaíso", ""),
    ("quillota-las-palmas", "Quillota Las Palmas", "Quillota", "Región de Valparaíso", ""),
    ("quilpue", "Quilpué", "Quilpué", "Región de Valparaíso", ""),
    ("renaca", "Reñaca", "Viña del Mar", "Región de Valparaíso", ""),
    ("san-antonio", "San Antonio", "San Antonio", "Región de Valparaíso", ""),
    ("san-felipe", "San Felipe", "San Felipe", "Región de Valparaíso", ""),
    ("santa-julia", "Santa Julia", "Viña del Mar", "Región de Valparaíso", ""),
    ("machali", "Machalí", "Machalí", "Región de O'Higgins", ""),
    ("rancagua-centro", "Rancagua Centro", "Rancagua", "Región de O'Higgins", ""),
    ("rengo", "Rengo", "Rengo", "Región de O'Higgins", ""),
    ("san-fernando", "San Fernando", "San Fernando", "Región de O'Higgins", ""),
    ("san-vicente", "San Vicente", "San Vicente de Tagua Tagua", "Región de O'Higgins", ""),
    ("curico-norte", "Curicó Norte", "Curicó", "Región del Maule", ""),
    ("talca", "Talca", "Talca", "Región del Maule", ""),
    ("talca-colin", "Talca Colín", "Talca", "Región del Maule", ""),
    ("chillan", "Chillán", "Chillán", "Región del Ñuble", ""),
    ("bio-bio", "Bío Bío", "Concepción", "Región del Biobío", "biobio|conce"),
    ("el-trebol", "El trébol", "Talcahuano", "Región del Biobío", ""),
    ("los-angeles", "Los Ángeles", "Los Ángeles", "Región del Biobío", ""),
    ("los-angeles-alemania", "Los Ángeles Alemania", "Los Ángeles", "Región del Biobío", ""),
]

# Cómo llama la central (simulador) a cada región.
REGION_CORTA = {
    "Región Metropolitana": "RM",
    "Región de Antofagasta": "II",
    "Región de Atacama": "III",
    "Región de Coquimbo": "IV",
    "Región de Valparaíso": "V",
    "Región de O'Higgins": "VI",
    "Región del Maule": "VII",
    "Región del Ñuble": "XVI",
    "Región del Biobío": "VIII",
}

# Tiendas con caja real (decisión de hrm, guía §0.3): un caso del demo es verdadero.
CAJAS_REALES = {"nataniel-cox": "minipc-lab-01"}

# Comunas que la central nombra distinto.
COMUNA_EN_CENTRAL = {"Santiago Centro": "Santiago"}
