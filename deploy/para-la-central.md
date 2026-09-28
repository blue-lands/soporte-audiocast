# Pedido a la instancia de MediaFlow (#7): enlace al soporte en el panel de la central

Pedido de hrm, 2026-09-28: al entrar a `https://central.mediaflow.cl/` debe haber un enlace que abra el soporte.
Se hace en el repo (`central/dashboard.html`, rama `feature/local-first`) y se despliega desde el #7. En vps4 no se
edita código de la central.

## El cambio

En la barra superior, justo antes de `<div class="sesion" id="sesion" hidden>`:

```html
    <a class="act" href="/soporte/" style="text-decoration:none">Soporte</a>
```

Usa la clase `.act` que ya existe (la del botón «Salir»). Es un enlace normal, en la misma pestaña o en otra: da igual.

## Qué hay que saber

- **El soporte no tiene entrada propia.** Entra quien tiene sesión abierta en la central. La galleta `ac_session`
  (`Path=/`) llega sola a `/soporte/`; esa app se la muestra a la central con `GET /api/me` y usa el `user` que responde.
  No necesita token de operador para eso.
- **Solo vale la sesión con usuario y clave.** Quien entra a la central con «entrar con un token» tiene el token en
  `localStorage`, no una galleta: el soporte no lo reconoce y lo devuelve a la central.
- **No cambiar** el nombre de la galleta (`ac_session`), su `Path=/`, ni la forma de la respuesta de `/api/me`
  (`{"user": "...", "login": true}`, 401 sin sesión) sin avisar. Si cambian, en el soporte son dos variables
  (`CENTRAL_GALLETA`, `CENTRAL_PANEL`) o `app/central.py`.
- **La ruta `/soporte` está reservada**: la atiende nginx antes de llegar a la central.
- Siguen pendientes: token de operador `soporte` para `GET /api/units` y un **rol de solo lectura**.
