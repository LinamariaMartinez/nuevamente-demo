"""Vista interactiva de quiz (capa 2): el estudiante responde, califica y ve las justificaciones."""

import streamlit as st


def mostrar(paquete, items):
    clave = f"quiz_{paquete.id_paquete}"
    for numero, pregunta in enumerate(items, start=1):
        st.markdown(f"**{numero}. {pregunta.pregunta}**")
        st.radio(f"Respuesta a la pregunta {numero}", pregunta.opciones, index=None,
                 key=f"{clave}_{numero}", label_visibility="collapsed")
    if st.button("Calificar", key=f"{clave}_calificar", type="primary"):
        st.session_state[f"{clave}_calificado"] = True
    if not st.session_state.get(f"{clave}_calificado"):
        return
    aciertos = 0
    for numero, pregunta in enumerate(items, start=1):
        elegida = st.session_state.get(f"{clave}_{numero}")
        correcta = pregunta.opciones[pregunta.respuesta_correcta]
        if elegida == correcta:
            aciertos += 1
            st.success(f"{numero}. Correcto. {pregunta.justificacion}")
        elif elegida is None:
            st.warning(f"{numero}. Sin responder. La respuesta era: {correcta}. {pregunta.justificacion}")
        else:
            st.error(f"{numero}. Incorrecto. La respuesta era: {correcta}. {pregunta.justificacion}")
    st.metric("Tu puntaje", f"{aciertos} de {len(items)}")
