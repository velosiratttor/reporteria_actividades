import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import date

# =========================
# Config
# =========================
SPREADSHEET_ID = "1ewnUoNHS9Dlk4TYz3psBiWFjARDFOSqWS81Ma5N97RI"
SERVICE_JSON = "envio-487119-b8d305894e66.json"

TAB_CT = "ct"   # debe existir EXACTO en tu Google Sheet
TAB_CTP = "ctp" # debe existir EXACTO en tu Google Sheet

CSV_ANALISTAS = "analistas.csv"   # columna esperada: analistas (o cambia abajo)
CSV_CENTROS_CT = "centros.csv"    # columna esperada: centros (o cambia abajo)
CSV_CENTROS_CTP = "ctp.csv"       # columna esperada: ctp (o cambia abajo)
CSV_ACTIVIDADES= "actividades.csv" # columna esperada: actividades
CSV_ACTIVIDADES_CTP= "actividades_ctp.csv"
# Encabezados EXACTOS del Google Sheet (fila 1)
SHEET_COLS = [
    "Especialista",
    "Fecha de recepcion",
    "Fecha de Atención",
    "Centro Tecnológico/Área Nivel Central",
    "TIPO DE ATENCION",
    "Solicitud",
]

TIPOS_ATENCION = ["Presencial", "Virtual", "Telefónica", "Correo", "Otro"]

# =========================
# Helpers
# =========================
@st.cache_data
def cargar_lista_csv(path: str, col: str) -> list[str]:
    try:
        df = pd.read_csv(path, dtype=str, on_bad_lines="skip")
    except pd.errors.ParserError:
        df = pd.read_csv(path, sep=";", dtype=str, on_bad_lines="skip")

    df.columns = (
        df.columns.astype(str)
        .str.replace("\u00A0", " ", regex=False)
        .str.strip()
    )

    if col not in df.columns:
        raise ValueError(f"En {path} no existe la columna '{col}'. Columnas: {list(df.columns)}")

    serie = (
        df[col]
        .dropna()
        .astype(str)
        .str.replace("\u00A0", " ", regex=False)
        .str.strip()
    )
    return sorted({x for x in serie.tolist() if x})


@st.cache_resource
def get_gspread_client():
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = Credentials.from_service_account_file(SERVICE_JSON, scopes=scopes)
    return gspread.authorize(creds)


def fila_valida(r: dict) -> bool:
    return all(str(r.get(k, "")).strip() for k in SHEET_COLS)


def subir_a_sheets(tab_name: str, filas: list[dict]):
    client = get_gspread_client()
    sh = client.open_by_key(SPREADSHEET_ID)

    # Diagnóstico para evitar "Error: ct/ctp" sin explicación
    tabs = [ws.title for ws in sh.worksheets()]
    if tab_name not in tabs:
        raise ValueError(f"No existe la pestaña '{tab_name}'. Pestañas disponibles: {tabs}")

    ws = sh.worksheet(tab_name)

    values = [[f.get(c, "") for c in SHEET_COLS] for f in filas]
    ws.append_rows(values, value_input_option="USER_ENTERED")


# =========================
# UI
# =========================
st.title("Formulario CT / CTP → Google Sheets (solo fechas)")

if st.button("🔄 Recargar catálogos (CSV)"):
    st.cache_data.clear()
    st.rerun()

# Catálogos (OJO: si tus columnas reales son 'nombre' y 'centro', cámbialas aquí)
ANALISTAS = cargar_lista_csv(CSV_ANALISTAS, "analistas")
CENTROS_CT = cargar_lista_csv(CSV_CENTROS_CT, "centros")
CENTROS_CTP = cargar_lista_csv(CSV_CENTROS_CTP, "ctp")
ACTIVIDADES=cargar_lista_csv(CSV_ACTIVIDADES,"actividades")
ACTIVIDADES_CTP=cargar_lista_csv(CSV_ACTIVIDADES_CTP,"actividades_ctp")
tipo_label = st.radio(
    "Tipo de centro",
    ["Centro Tecnológico (ct)", "Centro Privado (ctp)"],
    horizontal=True,
)
TAB_NAME = TAB_CT if tipo_label.startswith("Centro Tecnológico") else TAB_CTP
centros_opciones = CENTROS_CT if TAB_NAME == TAB_CT else CENTROS_CTP
actividades_opciones = ACTIVIDADES if TAB_NAME == TAB_CT else ACTIVIDADES_CTP
state_key = f"registros_{TAB_NAME}"

if state_key not in st.session_state:
    st.session_state[state_key] = []

st.caption(f"📌 Se guardará en la hoja/pestaña: **{TAB_NAME}**")

# =========================
# Formulario
# =========================
with st.form("agregar"):
    especialista = st.selectbox("Especialista *", ANALISTAS)

    c1, c2 = st.columns(2)
    with c1:
        fecha_recep = st.date_input("Fecha de recepcion *", value=date.today())
    with c2:
        fecha_atn = st.date_input("Fecha de Atención *", value=date.today())

    centro_area = st.selectbox("Centro Tecnológico/Área Nivel Central *", centros_opciones)
    tipo_atencion = st.selectbox("TIPO DE ATENCION *", TIPOS_ATENCION)
    solicitud = st.selectbox("Solicitud *",actividades_opciones)

    agregar = st.form_submit_button("Agregar a la tabla")

if agregar:
    fila = {
        "Especialista": str(especialista).strip(),
        "Fecha de recepcion": fecha_recep.isoformat(),  # SOLO FECHA
        "Fecha de Atención": fecha_atn.isoformat(),     # SOLO FECHA
        "Centro Tecnológico/Área Nivel Central": str(centro_area).strip(),
        "TIPO DE ATENCION": str(tipo_atencion).strip(),
        "Solicitud": str(solicitud).strip(),
    }   

    if not fila_valida(fila):
        st.error("Todos los campos son obligatorios.")
    else:
        st.session_state[state_key].append(fila)
        st.success("Agregado ✅")

st.divider()

# =========================
# Tabla editable + Envío
# =========================
st.subheader(f"Vista previa editable ({TAB_NAME})")

registros = st.session_state[state_key]
if not registros:
    st.info("Aún no hay registros.")
    st.stop()

df = pd.DataFrame(registros)

# asegurar columnas y orden
for c in SHEET_COLS:
    if c not in df.columns:
        df[c] = ""
df = df[SHEET_COLS]

edited_df = st.data_editor(
    df,
    use_container_width=True,
    num_rows="dynamic",
)

st.session_state[state_key] = edited_df.to_dict(orient="records")

c1, c2 = st.columns([1, 1])
with c1:
    if st.button("📤 Enviar a Google Sheets"):
        filas = st.session_state[state_key]
        invalidas = [i for i, r in enumerate(filas, start=1) if not fila_valida(r)]

        if invalidas:
            st.error(f"Hay filas incompletas: {invalidas}. Completa todo antes de enviar.")
        else:
            try:
                subir_a_sheets(TAB_NAME, filas)
                st.success(f"Enviado ✅ ({len(filas)} fila(s)) a la pestaña {TAB_NAME}.")
                st.session_state[state_key] = []
                st.rerun()
            except Exception as e:
                st.error(f"Error enviando a Sheets: {e}")

with c2:
    if st.button("🗑️ Limpiar tabla local"):
        st.session_state[state_key] = []
        st.rerun()