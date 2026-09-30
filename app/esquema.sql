-- Directorio de tiendas: asocia cada tienda del cliente con una caja de la central.
-- Lo llena `python -m app.cli cargar-tiendas` (app/directorio.py); no se edita a mano.
CREATE TABLE IF NOT EXISTS tiendas (
    id       TEXT PRIMARY KEY,           -- 'nataniel-cox'
    nombre   TEXT NOT NULL,              -- 'Nataniel Cox'
    comuna   TEXT NOT NULL,
    region   TEXT NOT NULL,              -- 'Región Metropolitana'
    unit_id  TEXT UNIQUE,                -- caja en la central; NULL = tienda sin equipo asociado
    site_id  TEXT,                       -- respaldo para encontrar la caja si cambia su unit_id
    alias    TEXT NOT NULL DEFAULT ''    -- otras formas de decirla, separadas por '|'
);

-- Cada vez que la asistente usó la herramienta consultar_tienda. Es lo que permite mostrar en el caso
-- qué vio la asistente y cómo estaba la caja en ese momento.
CREATE TABLE IF NOT EXISTS consultas (
    id              INTEGER PRIMARY KEY,
    conversation_id TEXT,                -- NULL si ElevenLabs no lo mandó
    momento         INTEGER NOT NULL,    -- segundos unix
    dicho           TEXT NOT NULL,       -- lo que la asistente buscó
    resultado       TEXT NOT NULL,       -- 'una' | 'varias' | 'ninguna'
    tienda_id       TEXT,                -- sin REFERENCES: la consulta sobrevive a una recarga del directorio
    frase           TEXT,                -- lo que se le dijo del equipo
    urgente         INTEGER,
    respuesta       TEXT NOT NULL,       -- JSON que recibió la asistente
    caja            TEXT                 -- JSON crudo de la caja; la asistente no lo recibe
);
CREATE INDEX IF NOT EXISTS consultas_conversacion ON consultas (conversation_id, id);

-- Un caso por conversación terminada (webhook de fin de ElevenLabs).
CREATE TABLE IF NOT EXISTS casos (
    conversation_id     TEXT PRIMARY KEY,
    agent_id            TEXT,
    canal               TEXT NOT NULL,   -- 'llamada' | 'whatsapp' | 'prueba' (navegador de ElevenLabs)
    telefono            TEXT,            -- de quien llamó, E.164
    inicio              INTEGER NOT NULL,
    duracion_s          INTEGER,
    tienda_id           TEXT,            -- la de la última consulta con una sola tienda; si no hubo, la que se entienda de la ficha
    -- Ficha ("Data collection" del agente, guía §0.4)
    tienda              TEXT,            -- como la nombró la persona
    nombre_contacto     TEXT,
    problema            TEXT,            -- sin_audio | volumen | aviso_no_salio | musica | otro
    desde_cuando        TEXT,
    motivo              TEXT,
    resumen             TEXT,            -- el de la ficha; si falta, el de ElevenLabs
    urgencia            INTEGER,         -- 1, 0 o NULL (no se supo)
    resuelto_en_llamada INTEGER,
    requiere_tecnico    INTEGER,
    -- Resto
    exitosa             INTEGER,
    motivo_corte        TEXT,
    transcripcion       TEXT NOT NULL,   -- JSON: [{"rol": "asistente"|"persona", "mensaje": …, "segundo": …}]
    costo               TEXT,
    recibido            INTEGER NOT NULL,
    avisado             INTEGER NOT NULL DEFAULT 0,  -- ya se mandó el aviso de caso urgente
    -- Número del caso para la persona (N° 0003): correlativo, se asigna al llegar. Índice único en db._migrar.
    numero              INTEGER,
    -- WhatsApp a quien llamó (app/whatsapp.py). NULL = no se ha procesado.
    whatsapp_estado     TEXT,            -- 'enviando' | 'enviado' | 'omitido' | 'error'
    whatsapp_detalle    TEXT,            -- por qué se omitió o qué error hubo; nunca la clave
    whatsapp_momento    INTEGER
);
CREATE INDEX IF NOT EXISTS casos_inicio ON casos (inicio DESC);
