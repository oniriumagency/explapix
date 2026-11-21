# Prototipo: escena del pulpo en HyperFrames

Prueba aislada (no forma parte del pipeline). Recrea el tramo 0:30.7–0:43.3 del short del pulpo
(capítulo «El corazón que se apaga»: CTA de guardar + «el corazón principal se detiene») con
[HyperFrames](https://hyperframes.heygen.com) 0.9.74, para compararlo con la versión en Manim.

Todo está en `index.html`: HTML/SVG + GSAP. La animación continua (cámara viva, estrellas,
tentáculos, latido, parpadeo, burbujas) es procedural y determinista; los eventos (pop, moods,
CTA, subtítulos) son tweens de GSAP en una línea de tiempo pausada.

## Correr

```bash
mkdir -p assets
cp ../../fonts/Fredoka.ttf ../../fonts/Nunito.ttf assets/
cp node_modules/hyperframes/dist/vendor/npm/gsap@3.15.0/dist/gsap.min.js assets/   # o desde npm i gsap
# narración/mezcla del tramo (12.6 s) del short del pulpo:
ffmpeg -i short-pulpo-vista-previa.mp4 -ss 30.75 -t 12.6 -vn -ac 1 -ar 48000 assets/narracion.wav
npx hyperframes@0.9.74 telemetry disable
npx hyperframes@0.9.74 check
npx hyperframes@0.9.74 render -o pulpo.mp4
```
