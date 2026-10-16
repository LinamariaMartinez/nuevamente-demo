"""Vista de flashcards (v2.2): tarjeta que se voltea, progreso y Lo sé / Repasar.

Todo pasa dentro de un iframe (st.iframe con HTML propio): voltear, moverse y marcar no recargan la app.
Las marcas viven en el componente y no se guardan (spec §6.3).
"""

import json

import streamlit as st

ALTO = 470
# Colores de "Bosque sereno" para cada modo; los contrastes se prueban en tests/test_interfaz_flashcards.py
COLORES = {
    "light": {"fondo": "#F5F7F5", "texto": "#142E2A", "frente": "#205E58", "texto_frente": "#FFFFFF",
              "dorso": "#FFFFFF", "borde": "#205E58", "suave": "#D6E2DC", "boton": "#FFFFFF",
              "borde_boton": "#7D948B", "si_fondo": "#DCFCE7", "si_texto": "#166534",
              "rep_fondo": "#FEF3C7", "rep_texto": "#854D0E", "punto_si": "#166534", "punto_rep": "#B7791F"},
    "dark": {"fondo": "#14201E", "texto": "#EAF2EF", "frente": "#2E6F66", "texto_frente": "#FFFFFF",
             "dorso": "#1E2B28", "borde": "#7DC1B0", "suave": "#2E3F3B", "boton": "#1E2B28",
             "borde_boton": "#6B8A81", "si_fondo": "#14532D", "si_texto": "#86E0AC",
             "rep_fondo": "#453313", "rep_texto": "#F5CD78", "punto_si": "#86E0AC", "punto_rep": "#F5CD78"},
}

PLANTILLA = """<!doctype html>
<html lang="es"><head><meta charset="utf-8">
<link href="https://fonts.googleapis.com/css2?family=Source+Sans+3:wght@400;600;700&display=swap" rel="stylesheet">
<style>
  body { margin:0; font-family:'Source Sans 3',sans-serif; background:__fondo__; color:__texto__; }
  .zona { padding:6px 4px; }
  .progreso { display:flex; justify-content:space-between; font-size:15px; margin-bottom:8px; }
  .barra { height:6px; background:__suave__; border-radius:3px; margin-bottom:16px; }
  .barra i { display:block; height:6px; border-radius:3px; background:__frente__; transition:width .3s; }
  .escena { perspective:1200px; height:280px; cursor:pointer; outline:none; }
  .escena:focus-visible { outline:3px solid __borde__; outline-offset:4px; border-radius:16px; }
  .carta { position:relative; width:100%; height:100%; transition:transform .5s cubic-bezier(.2,.7,.2,1);
           transform-style:preserve-3d; }
  .carta.volteada { transform:rotateY(180deg); }
  .cara { position:absolute; inset:0; backface-visibility:hidden; border-radius:16px; display:flex;
          flex-direction:column; align-items:center; justify-content:center; padding:28px; text-align:center;
          box-sizing:border-box; box-shadow:0 6px 18px rgba(0,0,0,.18); }
  .frente { background:__frente__; color:__texto_frente__; }
  .dorso { background:__dorso__; color:__texto__; border:2px solid __borde__; transform:rotateY(180deg); }
  .etiqueta { position:absolute; top:14px; left:18px; font-size:12px; letter-spacing:.08em; text-transform:uppercase; }
  .pregunta { font-size:26px; font-weight:700; line-height:1.25; }
  .respuesta { font-size:19px; line-height:1.5; }
  .pista { margin-top:14px; font-size:15px; }
  .ayuda { position:absolute; bottom:14px; font-size:13px; }
  .acciones { display:flex; gap:10px; justify-content:center; margin-top:16px; flex-wrap:wrap; }
  button { padding:9px 16px; border-radius:8px; font-weight:600; font-size:15px; cursor:pointer;
           border:1px solid __borde_boton__; background:__boton__; color:__texto__; font-family:inherit; }
  button:focus-visible { outline:3px solid __borde__; outline-offset:2px; }
  button.si { background:__si_fondo__; color:__si_texto__; border-color:__si_texto__; }
  button.rep { background:__rep_fondo__; color:__rep_texto__; border-color:__rep_texto__; }
  .puntos { display:flex; gap:6px; justify-content:center; margin-top:14px; }
  .puntos span { width:10px; height:10px; border-radius:5px; background:__suave__; }
  .puntos .ok { background:__punto_si__; } .puntos .rep { background:__punto_rep__; }
  .puntos .actual { outline:2px solid __borde__; outline-offset:2px; }
  @media (prefers-reduced-motion: reduce) { .carta, .barra i { transition:none; } }
</style></head>
<body><div class="zona">
  <div class="progreso" aria-live="polite">
    <span>Tarjeta <b id="numero">1</b> de <span id="total"></span></span>
    <span>Lo sé: <b id="sabes">0</b> · Repasar: <b id="repasar">0</b></span>
  </div>
  <div class="barra"><i id="barra"></i></div>
  <div class="escena" id="escena" tabindex="0" role="button" aria-label="Voltear la tarjeta">
    <div class="carta" id="carta">
      <div class="cara frente"><span class="etiqueta">Pregunta</span><div class="pregunta" id="pregunta"></div>
        <span class="ayuda">Clic o espacio para ver la respuesta</span></div>
      <div class="cara dorso"><span class="etiqueta">Respuesta</span><div class="respuesta" id="respuesta"></div>
        <div class="pista" id="pista"></div></div>
    </div>
  </div>
  <div class="acciones">
    <button id="anterior">← Anterior</button>
    <button class="rep" id="marcar_repasar">Repasar</button>
    <button class="si" id="marcar_se">Lo sé</button>
    <button id="siguiente">Siguiente →</button>
  </div>
  <div class="puntos" id="puntos"></div>
</div>
<script>
const TARJETAS = __DATOS__;
let actual = 0;
const marcas = TARJETAS.map(function () { return ""; });
const $ = function (id) { return document.getElementById(id); };

function pintar() {
  const t = TARJETAS[actual];
  $("carta").classList.remove("volteada");
  $("pregunta").textContent = t.frente;
  $("respuesta").textContent = t.dorso;
  $("pista").textContent = t.pista ? "Pista: " + t.pista : "";
  $("numero").textContent = actual + 1;
  $("total").textContent = TARJETAS.length;
  $("barra").style.width = ((actual + 1) / TARJETAS.length * 100) + "%";
  $("sabes").textContent = marcas.filter(function (m) { return m === "ok"; }).length;
  $("repasar").textContent = marcas.filter(function (m) { return m === "rep"; }).length;
  $("anterior").disabled = actual === 0;
  $("siguiente").disabled = actual === TARJETAS.length - 1;
  const puntos = $("puntos");
  puntos.textContent = "";
  marcas.forEach(function (marca, i) {
    const punto = document.createElement("span");
    punto.className = marca + (i === actual ? " actual" : "");
    puntos.appendChild(punto);
  });
}
function voltear() { $("carta").classList.toggle("volteada"); }
function mover(paso) { actual = Math.max(0, Math.min(TARJETAS.length - 1, actual + paso)); pintar(); }
function marcar(valor) { marcas[actual] = valor; if (actual < TARJETAS.length - 1) { actual += 1; } pintar(); }

$("escena").addEventListener("click", voltear);
$("anterior").addEventListener("click", function () { mover(-1); });
$("siguiente").addEventListener("click", function () { mover(1); });
$("marcar_se").addEventListener("click", function () { marcar("ok"); });
$("marcar_repasar").addEventListener("click", function () { marcar("rep"); });
document.addEventListener("keydown", function (e) {
  if (e.target.tagName === "BUTTON") { return; }
  if (e.code === "Space") { e.preventDefault(); voltear(); }
  if (e.code === "ArrowRight") { mover(1); }
  if (e.code === "ArrowLeft") { mover(-1); }
});
pintar();
</script></body></html>
"""


def construir_html(items, oscuro=False):
    """HTML completo del componente. El texto va como JSON y se pone con textContent: nunca se interpreta como HTML."""
    datos = [{"frente": i.frente, "dorso": i.dorso, "pista": i.pista_didactica or ""} for i in items]
    # "</" partiría el <script>: en JSON, "<\/" es el mismo texto
    datos_json = json.dumps(datos, ensure_ascii=False).replace("</", "<\\/")
    html = PLANTILLA.replace("__DATOS__", datos_json)
    for nombre, color in COLORES["dark" if oscuro else "light"].items():
        html = html.replace(f"__{nombre}__", color)
    return html


def mostrar(paquete, items):
    oscuro = st.context.theme.type == "dark"  # None en pruebas o si el navegador no lo informa: claro
    st.iframe(construir_html(items, oscuro), height=ALTO)
