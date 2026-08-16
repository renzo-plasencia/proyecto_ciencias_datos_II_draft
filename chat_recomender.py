# chat_recomendador.py
# Popup tipo chat que recomienda un producto financiero (ahorro/DPF o TC)
# según respuestas simples del usuario.

import streamlit as st


# ============================================================
# HELPERS DE ESTADO
# ============================================================

def _bot_say(texto: str) -> None:
    st.session_state.chat_history.append(("assistant", texto))


def _user_say(texto: str, key: str, value) -> None:
    st.session_state.chat_history.append(("user", texto))
    st.session_state.chat_answers[key] = value


def _reset_quiz() -> None:
    st.session_state.chat_step = 0
    st.session_state.chat_answers = {}
    st.session_state.chat_history = []
    st.session_state.chat_resultado_mostrado = False


def _cerrar_chat() -> None:
    st.session_state.chat_open = False


# ============================================================
# LÓGICA DE RECOMENDACIÓN
# ============================================================

def _recomendar(cuentas_df, dpf_df, tc_df) -> str:
    a = st.session_state.chat_answers
    objetivo = a.get("objetivo")

    if objetivo == "ahorro":
        if a.get("liquidez") == "si":
            df = cuentas_df[cuentas_df["monto_minimo_apertura"] <= a.get("monto", 0)]
            tipo = "Cuenta de Ahorro"
            col_producto = "producto_nombre"
        else:
            df = dpf_df[dpf_df["monto_minimo_num"] <= a.get("monto", 0)]
            tipo = "Depósito a Plazo Fijo"
            col_producto = "producto"

        if df.empty:
            return f"No encontré un {tipo.lower()} que calce con ese monto mínimo. Prueba con un monto mayor."

        mejor = df.sort_values("trea_num", ascending=False).iloc[0]
        return (
            f"Te recomiendo **{tipo}** en **{mejor['banco']}** ({mejor[col_producto]}), "
            f"con una TREA de **{mejor['trea_num']}%**."
        )

    else:
        df = tc_df[tc_df["ingreso_min_num"] <= a.get("ingreso", 0)]
        if a.get("preferencia") == "millas":
            df_pref = df[df["acumula_millas_puntos"] == True]
            df = df_pref if not df_pref.empty else df

        if df.empty:
            return "No encontré una tarjeta que califique con ese ingreso. Prueba con un ingreso mayor."

        mejor = df.sort_values("ingreso_min_num", ascending=False).iloc[0]
        return f"Te recomiendo la tarjeta **{mejor['producto_nombre']}** de **{mejor['banco']}**."


# ============================================================
# POPUP (DIALOG) CON EL FLUJO DE PREGUNTAS
# ============================================================

@st.dialog("Asistente de recomendación 💬")
def _quiz_dialog(cuentas_df, dpf_df, tc_df) -> None:
    # Inicializar historial en el paso 0 si está vacío
    if st.session_state.chat_step == 0 and not st.session_state.chat_history:
        _bot_say("¡Hola! ¿Qué buscas hoy?")

    # Pinta todo el historial de chat guardado
    for rol, texto in st.session_state.chat_history:
        with st.chat_message(rol):
            st.markdown(texto)

    step = st.session_state.chat_step
    answers = st.session_state.chat_answers

    # --- Paso 0: objetivo general ---
    if step == 0:
        c1, c2 = st.columns(2)
        if c1.button("💰 Hacer crecer mi dinero", use_container_width=True):
            _user_say("Hacer crecer mi dinero", "objetivo", "ahorro")
            _bot_say("¿Vas a necesitar ese dinero en los próximos meses?")
            st.session_state.chat_step = 1
            st.rerun()

        if c2.button("💳 Comprar / financiar algo", use_container_width=True):
            _user_say("Comprar o financiar algo", "objetivo", "tc")
            _bot_say("¿Cuál es tu ingreso mensual aproximado?")
            st.session_state.chat_step = 1
            st.rerun()

    # --- Paso 1 (rama ahorro): liquidez ---
    elif step == 1 and answers.get("objetivo") == "ahorro":
        c1, c2 = st.columns(2)
        if c1.button("Sí, puede que lo necesite", use_container_width=True):
            _user_say("Sí, puede que lo necesite", "liquidez", "si")
            _bot_say("¿Cuánto tienes disponible para empezar?")
            st.session_state.chat_step = 2
            st.rerun()

        if c2.button("No, lo puedo dejar quieto", use_container_width=True):
            _user_say("No, lo puedo dejar quieto", "liquidez", "no")
            _bot_say("¿Cuánto tienes disponible para empezar?")
            st.session_state.chat_step = 2
            st.rerun()

    # --- Paso 1 (rama TC): ingreso ---
    elif step == 1 and answers.get("objetivo") == "tc":
        opciones = [("Menos de S/1500", 1000), ("S/1500 - S/5000", 2000), ("Más de S/5000", 6000)]
        for label, val in opciones:
            if st.button(label, key=f"ing_{val}", use_container_width=True):
                _user_say(label, "ingreso", val)
                _bot_say("¿Qué prefieres?")
                st.session_state.chat_step = 2
                st.rerun()

    # --- Paso 2 (rama ahorro): monto disponible ---
    elif step == 2 and answers.get("objetivo") == "ahorro":
        opciones = [("Menos de S/500", 400), ("S/500 - S/2000", 1500), ("Más de S/2000", 5000)]
        for label, val in opciones:
            if st.button(label, key=f"monto_{val}", use_container_width=True):
                _user_say(label, "monto", val)
                st.session_state.chat_step = 3
                st.rerun()

    # --- Paso 2 (rama TC): preferencia ---
    elif step == 2 and answers.get("objetivo") == "tc":
        c1, c2 = st.columns(2)
        if c1.button("Sin membresía / simple", use_container_width=True):
            _user_say("Sin membresía / lo más simple", "preferencia", "simple")
            st.session_state.chat_step = 3
            st.rerun()

        if c2.button("Acumular millas", use_container_width=True):
            _user_say("Acumular millas / beneficios viaje", "preferencia", "millas")
            st.session_state.chat_step = 3
            st.rerun()

    # --- Paso 3: resultado final ---
    elif step == 3:
        if not st.session_state.chat_resultado_mostrado:
            resultado = _recomendar(cuentas_df, dpf_df, tc_df)
            _bot_say(resultado)
            st.session_state.chat_resultado_mostrado = True
            st.rerun()

        c1, c2 = st.columns(2)
        if c1.button("🔁 Volver a empezar", use_container_width=True):
            _reset_quiz()
            st.rerun()
        if c2.button("✖️ Cerrar", use_container_width=True):
            _cerrar_chat()
            st.rerun()


# ============================================================
# FUNCIÓN PÚBLICA (la que se llama desde cada página)
# ============================================================

def render_chat_recomendador(cuentas_df, dpf_df, tc_df) -> None:
    """
    Muestra un botón flotante (FAB) fijo en la esquina inferior derecha,
    visible en cualquier página, que abre el popup de recomendación.
    """
    st.markdown(
        """
        <style>
        div.st-key-chat_fab_btn {
            position: fixed !important;
            bottom: 30px !important;
            right: 30px !important;
            z-index: 99999 !important;
            width: 60px !important;
            height: 60px !important;
        }

        div.st-key-chat_fab_btn button {
            width: 60px !important;
            height: 60px !important;
            border-radius: 50% !important;
            background-color: #FF4B4B !important;
            border: none !important;
            box-shadow: 0 4px 12px rgba(0,0,0,0.35) !important;
            padding: 0 !important;
        }

        div.st-key-chat_fab_btn button * {
            color: #FFFFFF !important;
            font-size: 26px !important;
            background: transparent !important;
        }

        div.st-key-chat_fab_btn button:hover {
            background-color: #E03E3E !important;
        }

        div.st-key-chat_fab_btn button:focus,
        div.st-key-chat_fab_btn button:active {
            background-color: #C03434 !important;
            outline: none !important;
            box-shadow: 0 4px 12px rgba(0,0,0,0.5) !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    if "chat_open" not in st.session_state:
        st.session_state.chat_open = False
    if "chat_step" not in st.session_state:
        _reset_quiz()

    if st.button("🤖", key="chat_fab_btn", help="¿No sabes qué elegir? Pregúntame", type="primary"):
        _reset_quiz()
        st.session_state.chat_open = True

    # CLAVE: mientras chat_open sea True, se vuelve a abrir en CADA rerun,
    # no solo cuando se hace clic en el botón flotante.
    if st.session_state.chat_open:
        _quiz_dialog(cuentas_df, dpf_df, tc_df)