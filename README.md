# Explapix: pipeline automático de videos explicativos

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

# Prueba sin IA (usa el ejemplo del refrigerador)
python make_video.py --storyboard examples/refrigerador/storyboard.json --scene examples/refrigerador/scene.py

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

- `explapix/kit.py`: estilo visual v2 (fondo vivo, formas con volumen, brillos, caritas, fuentes Fredoka/Nunito en `fonts/`), ayudantes de los 12 principios de animación (pop_in, squash_bounce, anticipate_move, move_along_arc, jelly, emphasize, exit_out, cascade, idle_*, cámara focus/reset) y la base que sincroniza cada segmento con su audio. La docstring del archivo tiene la tabla principio → ayudante.
- `explapix/llm.py`: prompts de guion, escena y respuestas a comentarios.
- `explapix/tts.py` + `explapix/tts_worker.py`: voz (los motores con PyTorch corren en `.venv-tts` / `.venv-kokoro`). `python -m explapix.tts say "texto" -o prueba.wav -e kokoro` para probar.
- `explapix/render.py`: render/mezcla.
- `explapix/youtube.py`: subida y comentarios (YouTube Data API v3, cuota gratis ~5 videos/día).

Fuentes Fredoka y Nunito: SIL Open Font License (`fonts/OFL-*.txt`).

## Explapix Studio (panel web)

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
