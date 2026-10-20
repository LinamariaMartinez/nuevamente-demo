"""Vista interactiva de flashcards (capa 2): una tarjeta a la vez; se voltea para ver la respuesta."""

import streamlit as st


def _mover(clave, paso, total):
    actual = st.session_state.get(f"{clave}_indice", 0)
    st.session_state[f"{clave}_indice"] = max(0, min(total - 1, actual + paso))
    st.session_state[f"{clave}_volteada"] = False


def _voltear(clave):
    st.session_state[f"{clave}_volteada"] = not st.session_state.get(f"{clave}_volteada", False)


def mostrar(paquete, items):
    clave = f"flashcard_{paquete.id_paquete}"
    total = len(items)
    indice = min(st.session_state.get(f"{clave}_indice", 0), total - 1)
    tarjeta = items[indice]
    st.caption(f"Tarjeta {indice + 1} de {total}")
    with st.container(border=True):
        if st.session_state.get(f"{clave}_volteada", False):
            st.markdown(f"### {tarjeta.dorso}")
            if tarjeta.pista_didactica:
                st.caption(f"Pista: {tarjeta.pista_didactica}")
        else:
            st.markdown(f"### {tarjeta.frente}")
    anterior, voltear, siguiente = st.columns(3)
    anterior.button("Anterior", key=f"{clave}_anterior", disabled=indice == 0,
                    on_click=_mover, args=(clave, -1, total))
    voltear.button("Voltear", key=f"{clave}_voltear", on_click=_voltear, args=(clave,))
    siguiente.button("Siguiente", key=f"{clave}_siguiente", disabled=indice == total - 1,
                     on_click=_mover, args=(clave, 1, total))
