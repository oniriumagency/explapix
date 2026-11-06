# Factos Didácticos: pipeline automático de videos explicativos

> Nombre del canal: **Factos Didácticos**. Internamente el código, la carpeta, el repo y el servicio siguen llamándose `explapix` para no romper nada.

Tema → guion (Claude) → voz (Chatterbox/Kokoro/Piper, local) → animación (Manim, local) → MP4 vertical 1080×1920 → YouTube Shorts → respuestas a comentarios.

## Por qué Manim

| Opción | Costo | Corre en servidor sin GPU | Fácil de generar con IA | Comentario |
|---|---|---|---|---|
| **Manim Community** (elegida) | Gratis (MIT) | Sí, solo CPU | Muy fácil (Python) | Estilo diagrama limpio, ideal para "cómo funciona". ~2 min de render (voz + animación) por video de 40 s en Magne Server. |
| Motion Canvas | Gratis (MIT) | Sí, pero render vía navegador headless | Bien (TypeScript) | Bonito, pero el render automático sin interfaz es más frágil. |
| Remotion | Licencia de pago para empresas de 4+ personas | Sí (Chrome headless) | Bien (React) | Mejor para plantillas con video/fotos que para diagramas. |
| Blender headless | Gratis | Lento sin GPU (Cycles); EEVEE necesita GPU | Difícil: la IA falla mucho armando escenas 3D | Se ve más "3D", pero cada video cuesta horas de render y muchos reintentos. |

Voz (todo local y gratis, licencias que permiten monetizar):

| Motor | Licencia | Calidad | Velocidad (RTX 4060) |
|---|---|---|---|
| **Chatterbox Multilingual** (por defecto) | MIT | La más natural y expresiva; clona timbre de `voices/ref.wav` | ~2 s por frase (GPU, ~4 GB VRAM) |
| Kokoro-82M (`em_alex`, `ef_dora`) | Apache-2.0 | Limpia, algo plana | <1 s por frase |
| Piper | MIT | Robótica | instantánea en CPU |

Chatterbox añade una marca de agua inaudible (Perth) al audio. Para clonar **tu** voz, graba 10-20 s limpios en wav y ponlo en `voices/ref.wav`. Evitamos XTTS-v2, F5-TTS y Fish Speech porque sus licencias no permiten uso comercial. Guion y código de animación: **Claude API**, unos centavos de dólar por video. Si quieres costo cero absoluto, se puede cambiar por un modelo local con Ollama, pero baja la calidad del código de animación.

## Instalación (Magne Server)

```bash
bash setup_server.sh
cp .env.example .env   # pon tu ANTHROPIC_API_KEY
```

## Conectar YouTube (una sola vez)

1. En [Google Cloud Console](https://console.cloud.google.com/) crea un proyecto y habilita **YouTube Data API v3**.
2. Configura la pantalla de consentimiento OAuth (tipo externo) y agrega tu cuenta de Google como usuario de prueba.
3. En Credenciales, crea un **ID de cliente OAuth** de tipo **App de escritorio** y descárgalo.
4. Guárdalo en el servidor como `secrets/client_secret.json`.
5. La primera subida imprime una URL: ábrela en tu navegador, autoriza el canal y el token queda guardado en `secrets/token.json`.

## Uso

```bash
. .venv/bin/activate
set -a; . ./.env; set +a

# Prueba sin IA (ejemplos: refrigerador = kit v2, microondas = kit v3 dinámico)
python make_video.py --storyboard examples/refrigerador/storyboard.json --scene examples/refrigerador/scene.py
python make_video.py --storyboard examples/microondas/storyboard.json --scene examples/microondas/scene.py

# Video nuevo 100 % automático
python make_video.py --topic "Cómo funciona un microondas"

# Lote + subida (privado para revisar antes de publicar)
python make_video.py --topics temas.txt --upload --privacy private

# Comentarios: crea borradores; luego marca "approved": true y envía
python reply_comments.py
python reply_comments.py --send-approved
```

Cada video queda en `out/<fecha>-<tema>/` con `storyboard.json`, `scene.py`, `final.mp4` y `meta.json` (título, descripción, tags).

## Automatizar (cron)

```cron
# Un video diario a las 9:00 (sube privado), comentarios cada 2 horas
0 9 * * *   cd ~/explapix && .venv/bin/python make_video.py --topics cola.txt --upload --privacy private
0 */2 * * * cd ~/explapix && .venv/bin/python reply_comments.py
```

## Variables

| Variable | Default | Para qué |
|---|---|---|
| `ANTHROPIC_API_KEY` | (requerida) | Guion, animación y respuestas |
| `EXPLAPIX_MODEL` | `claude-opus-5-5` | Modelo de Claude |
| `EXPLAPIX_TTS` | `chatterbox` | `chatterbox`, `kokoro`, `piper` o `espeak` (solo pruebas) |
| `EXPLAPIX_VOICE_REF` | `voices/ref.wav` | Timbre a clonar con Chatterbox |
| `EXPLAPIX_CB_EXAGGERATION` / `EXPLAPIX_CB_CFG` | `0.6` / `0.4` | Emoción y ritmo de Chatterbox |
| `EXPLAPIX_KOKORO_VOICE` | `em_alex` | Voz Kokoro |
| `EXPLAPIX_PIPER_MODEL` | `voices/es_MX-claude-high.onnx` | Voz |
| `EXPLAPIX_YT_SECRETS` | `secrets/client_secret.json` | OAuth de YouTube |

## Estructura

- `explapix/kit.py`: kit v3 — fondo con moods de color por segmento (`segment(i, mood=...)`, `mood()`), cámara que se mueve, acerca y gira en paralelo (`cam_to`, `cam_sway`, `cam_reset`; los subtítulos quedan fijos), sistemas de partículas (`particles`: chispas, burbujas, calor, estrellas, confeti, frío, órbita, polvo) y vida constante (`alive`, `idle_wiggle`, `idle_pulse`, `idle_spin`). Además: estilo visual v2 (fondo vivo, formas con volumen, brillos, caritas, fuentes Fredoka/Nunito en `fonts/`), ayudantes de los 12 principios de animación (pop_in, squash_bounce, anticipate_move, move_along_arc, jelly, emphasize, exit_out, cascade, idle_*, cámara focus/reset) y la base que sincroniza cada segmento con su audio. La docstring del archivo tiene la tabla principio → ayudante.
- `explapix/llm.py`: prompts de guion, escena y respuestas a comentarios.
- `explapix/tts.py` + `explapix/tts_worker.py`: voz (los motores con PyTorch corren en `.venv-tts` / `.venv-kokoro`). `python -m explapix.tts say "texto" -o prueba.wav -e kokoro` para probar.
- `explapix/render.py`: render/mezcla.
- `explapix/youtube.py`: subida y comentarios (YouTube Data API v3, cuota gratis ~5 videos/día).

Fuentes Fredoka y Nunito: SIL Open Font License (`fonts/OFL-*.txt`).

## Factos Didácticos Studio (panel web)

Panel para revisar y controlar todo sin comandos: `http://100.96.241.48:8097` (por Tailscale; también `http://192.168.2.15:8097` en casa). Usuario `magne`, contraseña en `secrets/panel_password` (se genera sola, permisos 600, fuera de git).

| Pantalla | Para qué |
|---|---|
| Biblioteca | Videos con reproductor, guion por segmento, estado (por revisar / aprobado / rechazado / YouTube). Aprobar, Rechazar con nota, Regenerar (con Claude usando la nota, o solo voz/render gratis), editar título/descripción/tags y Subir a YouTube con confirmación (privado por defecto). |
| Nuevo | Uno o varios temas (uno por línea), indicaciones, voz y calidad. Botón de ejemplo sin IA. |
| Cola | Un trabajo a la vez (GPU), paso actual (guion → voz → animación → mezcla / subida) y log en vivo. Cancelar. |
| Comentarios | Borradores de `reply_comments.py`: editar, aprobar, descartar, buscar nuevos y «Enviar aprobados» con confirmación. |
| Voces | Muestras, voz por defecto y ajustes de Chatterbox/Kokoro, subir tu grabación como referencia, probar frases. |
| Sistema | Clave de Anthropic y YouTube (sin mostrar valores), conectar YouTube desde el navegador, cuota estimada del día, GPU y disco. |

Instalar/actualizar el servicio (systemd de usuario, arranca solo tras reiniciar): `bash deploy/instalar_panel.sh`.
Logs: `journalctl --user -u explapix-studio -f`. Tests: `.venv/bin/python -m pytest -q`.
Seguridad: nada se publica sin confirmación; `secrets/` y `.env` nunca se sirven por HTTP (solo rutas explícitas de videos, miniaturas, voces y fuentes).

## Estándar, calendario y motor de IA

- **Estándar del canal**: `config/estilo.yaml` (voz Chatterbox con emoción 0.6 / ritmo 0.4, HD, 40-50 s, moods, cámara, partículas, reglas). `llm.py` lo incluye en el prompt y usa `examples/microondas/scene.py` como ejemplo principal.
- **Motor de IA** (`EXPLAPIX_LLM` o `llm.motor` en el YAML):
  - `claude-code` (por defecto): usa el CLI `claude` ya iniciado con la suscripción de Claude del servidor (`claude -p`, sin herramientas, JSON validado, reintentos). Sin costo aparte. Si se alcanza el límite de uso, espera 30 min y reintenta (hasta 8 h) en vez de fallar.
  - `api`: API de Anthropic con `ANTHROPIC_API_KEY`.
- **Calendario** (`data/calendario.json`, pantalla «Calendario» del panel): 30 temas con gancho, título, caption de Instagram, comentario fijado, hora (CDMX) y guion. Se puede editar, reordenar y marcar estado. Con «Generar pendientes solo» activado, el panel genera uno a la vez con 20 min de pausa entre videos (`llm.pausa_entre_videos_min`). Las escenas escritas a mano van en `data/escenas/<id>.py` y tienen prioridad sobre la IA. Regenerar la base: `python scripts/calendario_base.py --force`.

## Instagram (Reels y comentarios)

Usa la «API de Instagram con inicio de sesión de Instagram» de Meta (cuenta profesional: empresa o creador).

1. En [developers.facebook.com](https://developers.facebook.com/) crea una app → agrega el producto **Instagram** → «API setup with Instagram login».
2. En «Business login settings» agrega la URL de redirección `https://localhost/` (o la que pongas en el panel).
3. En el panel → Sistema → Conectar Instagram pega el **Instagram App ID** y el **App Secret**, pulsa «Autorizar», inicia sesión y copia de vuelta la dirección a la que te lleva (no carga; es normal).
4. Mientras la app esté en modo desarrollo, tu cuenta debe estar agregada como «Instagram tester» en la app.

Permisos: `instagram_business_basic`, `instagram_business_content_publish`, `instagram_business_manage_comments`, `instagram_business_manage_insights`. El token dura 60 días y se renueva solo.

**Publicar Reels necesita una URL pública** (Meta descarga el video). `explapix/instagram.py` levanta un servidor que solo entrega ese archivo y lo expone con **Tailscale Funnel** en una ruta aleatoria durante la subida; al terminar lo cierra. Hay que activarlo una vez:
- En login.tailscale.com → DNS: habilitar **HTTPS Certificates**.
- En Access controls, agregar el atributo `funnel` a este servidor (`"nodeAttrs": [{"target": ["autogroup:member"], "attr": ["funnel"]}]`).
- En el servidor: `sudo tailscale set --operator=magne` (para usar `tailscale funnel` sin sudo).

Las subidas a Instagram y las respuestas a comentarios pasan por la misma aprobación del panel (botón + confirmación). La API no permite fijar comentarios: el «comentario fijado» del calendario se publica y fija a mano.

## Métricas

`update_stats.py` (botón «Actualizar métricas» en Sistema) guarda en cada `meta.json`: YouTube (vistas, likes, comentarios; y con YouTube Analytics: % medio visto, duración media, compartidos) e Instagram (alcance, reproducciones, guardados, compartidos, likes, comentarios). Sistema muestra los mejores videos y el promedio por categoría para elegir temas. Para YouTube Analytics habilita «YouTube Analytics API» en el proyecto de Google Cloud.
