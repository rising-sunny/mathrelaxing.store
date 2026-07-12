# Contexto del Proyecto: Integración TikTok (Orgánico y Ads)

Este documento resume todo el trabajo realizado en la integración de la tienda **Math Relaxing** con TikTok hasta la fecha, para facilitar la continuación del trabajo en otro equipo.

## 1. Estado de las Aplicaciones en TikTok
Actualmente tenemos dos aplicaciones registradas en el portal de desarrolladores de TikTok:

*   **App Orgánica (Content Posting API):**
    *   **Estado:** Aprobada para envíos a la "Bandeja de Entrada" (Drafts/Inbox).
    *   **Direct Post:** Se envió una revisión solicitando el permiso `video.publish` (Direct Post) para publicar directamente al feed sin pasar por borradores. Está en revisión.
    *   **Uso actual:** Funciona correctamente. Envía videos directamente a la bandeja de entrada de la cuenta vinculada.
*   **App de Anuncios (Marketing API - Ads):**
    *   **Nombre:** `MathRelaxingAds`
    *   **Estado:** **Pending** (En revisión por parte de TikTok, suele tardar 1-3 días hábiles).
    *   **Permisos solicitados:** Ad Account Management, Ads Management, Reporting, Creative Management.
    *   **Pendiente:** Obtener el `App ID` y `Secret` una vez sea aprobada para conectarla al backend.

## 2. Configuración de Correo Electrónico
Para superar la restricción de TikTok que exige un "correo empresarial", se configuró un alias/reenviador de correos a nivel de DNS en Namecheap:
*   Se crearon los registros **MX** apuntando a los servidores gratuitos de Namecheap (`eforward1.registrar-servers.com`, etc.).
*   Se configuró el alias `admin@mathrelaxing.store` para que reenvíe automáticamente cualquier correo hacia la cuenta personal de Gmail.
*   **Estado:** Operativo y validado por TikTok.

## 3. Generación Automática de Videos
El servidor (VPS en `5.78.125.169`) cuenta con un script en Python (`tiktok_chladni_video_v2.py`) que genera videos algorítmicos.
*   **Audio:** Se agregó una función de generación de ruido ambiental/frecuencias relajantes usando FFmpeg (Brown noise/Campanas).
*   **Salida:** El sistema ahora renderiza exitosamente a 50 FPS y exporta el video final con el audio sincronizado en `/var/www/mathrelaxing.store/static/video/tiktok_chladni_v2.mp4`.
*   **Validación:** Se generó y envió un video con sonido exitosamente.

## 4. Sistema de Auto-Publicación (Backend)
El script `services/tiktok_jobs.py` maneja la lógica de envío hacia TikTok.
*   **Descripciones:** Se intentó inyectar el texto/caption (título y descripción) en la carga útil (payload), pero se comprobó que la API de "Inbox" de TikTok **bloquea el texto por diseño**. Las descripciones se deben copiar y pegar manualmente hasta que aprueben el "Direct Post".
*   **Estado del Bot:** Actualmente el cron de auto-publicación está **PAUSADO** intencionalmente. 
*   **Cómo reanudarlo:** Para encenderlo nuevamente, cambia la variable `TIKTOK_AUTO_POST_ENABLED=1` en el archivo `.env` del servidor (`/var/www/mathrelaxing.store/.env`) y reinicia el servicio (`systemctl restart mathrelaxing`).

## 5. Próximos Pasos (Next Steps)
Para continuar con el desarrollo en esta u otra computadora, el plan a seguir es:

1.  **Monitorear Aprobaciones:** Revisar el portal de desarrolladores de TikTok hasta obtener la aprobación del "Direct Post" y la App de Ads.
2.  **Configurar Credenciales de Ads:** Una vez aprobada la App de Ads, extraer el `App ID` y `Secret` y guardarlos como variables de entorno.
3.  **Desarrollar Flujo OAuth de Ads:** Crear las rutas en FastAPI (`/admin/tiktok-ads/login` y `/admin/tiktok-ads/callback`) en el archivo `routers/admin.py` para vincular la cuenta publicitaria al backend.
4.  **Lógica de Creación de Campañas:** Desarrollar `services/tiktok_ads_service.py` para automatizar la creación de una Campaña, un Grupo de Anuncios y un Anuncio (usando el video generado) bajo un presupuesto límite o en estado "Pausado" para validación.
