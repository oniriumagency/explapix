# Factos Didácticos (código interno: explapix)

Canal de videos animados que explican cómo funcionan las cosas. Antes de tocar guiones, escenas,
voz, audio o publicación:

1. **Lee y respeta `config/reglas.yaml`.** Es la fuente única de las reglas del canal (marca, guion y
   duración, llamados a la acción, estilo visual, zona segura, voz, audio, publicación). Si una regla
   cambia, se cambia ahí; los prompts de `explapix/llm.py` y la página «Cómo funciona» la leen de ese
   archivo. No dupliques reglas en otros lados.
2. **Corre el verificador antes de entregar cualquier video:** `.venv/bin/python -m explapix.qa out/<carpeta>`
   (lo hace solo `make_video.py`). Un video solo se entrega como «por revisar» si pasa todos los checks;
   si no, queda como «necesita corrección» con el detalle en la Biblioteca del panel.
3. **Nada se publica ni se responde sin la aprobación de Magne** en el panel (http://100.96.241.48:8097).
4. Parámetros técnicos (voz, dB, cámara): `config/estilo.yaml`. Ejemplo de referencia de escena:
   `examples/microondas/scene.py`. Escenas escritas a mano: `data/escenas/`.
5. Tests del panel: `.venv/bin/python -m pytest -q`. El panel corre como `systemctl --user explapix-studio`;
   no lo reinicies mientras la Cola tiene un trabajo corriendo (lo interrumpe).
