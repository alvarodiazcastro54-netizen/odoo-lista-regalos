# Antes de llevarlo a producción

Todo lo de este repositorio se desarrolló y probó en un entorno **local**, con datos de demostración. Esta página reúne lo que hay que revisar antes de instalarlo en el Odoo de la empresa, la configuración de la promoción de inauguración y lo que quedó pendiente.

- [Lo que se probó y lo que no](#lo-que-se-probó-y-lo-que-no)
- [Lista de verificación](#lista-de-verificación)
- [Promoción de inauguración](#promoción-de-inauguración)
- [Pendientes](#pendientes)
- [Límites conocidos](#límites-conocidos)

## Lo que se probó y lo que no

| Se probó | No se probó |
| --- | --- |
| Instalación desde cero en Odoo 19 Community con PostgreSQL 16 | Con la localización peruana instalada |
| 25 pruebas automatizadas, incluida una de pantalla en Chrome | En una pantalla táctil real |
| La caja en Chrome, a 1366 × 768 y 1024 × 768, sin errores de consola | Otros navegadores y el ancho de un teléfono |
| Venta con regalo, dedicatoria, código de descuento y cobro en efectivo | Impresión en una impresora térmica real |
| El recibo conserva su letra y disposición con el tema | Productos con impuesto (IGV): los de demostración no tenían |
| Desinstalar el tema devuelve la caja a su aspecto estándar | Envío real de correos: el entorno no tenía servidor de correo |
| | Con el tema: cierre de caja y lista de clientes |

## Lista de verificación

**Antes de instalar**

- [ ] Hacer una copia de seguridad y probar primero en una **copia** de producción.
- [ ] Instalar fuera del horario de atención y con **todas las sesiones de caja cerradas**.
- [ ] Usar la imagen oficial de Odoo. `Dockerfile.pruebas` y `docker-compose.pruebas.yml` son solo para desarrollo.

**Configuración**

- [ ] Dar el permiso **Administrador** de Listas de regalos al menos a un usuario por empresa. Sin él, los avisos de exceso y los de listas sin responsable no tienen destinatario.
- [ ] Comprobar que los usuarios tienen la zona horaria `America/Lima`.
- [ ] En **Punto de venta › Configuración › Ajustes**, activar "Listas de regalos" en cada caja y, si se quiere el ticket sin precios para acompañar el regalo, el recibo básico.
- [ ] Marcar "Disponible en PdV" en los productos que se pondrán en las listas.
- [ ] Decidir si la aplicación **Contactos** debe seguir visible para los cajeros (ver [límites](#límites-conocidos)).

**Correo**

- [ ] Configurar el servidor de correo saliente. El módulo envía correos al dueño: lista activada, regalo recibido y recordatorio 7 días antes.
- [ ] Tener en cuenta que Odoo también envía un correo "Te asignaron…" por cada actividad a los usuarios cuya preferencia de notificación es correo. Quien no lo quiera puede cambiarla a "Odoo" en sus preferencias.

**Pruebas en la copia**

- [ ] Una venta con un producto **con IGV** y, si aplica, con la promoción: revisar total y desglose del ticket.
- [ ] Si se emite **boleta o factura electrónica** desde la caja: el descuento es una línea en negativo; confirmar con el proveedor de facturación que la acepta.
- [ ] Buscar una lista por **DNI**: la búsqueda es exacta contra el número de identificación del contacto; con la localización peruana conviene comprobar cómo queda guardado.
- [ ] Imprimir un ticket con leyenda y dedicatoria en la impresora real.
- [ ] Revisar con el tema el cierre de caja y la lista de clientes.

**El día de la puesta en marcha**

- [ ] Si alguna caja muestra "¡Ups! Ocurrió un error…" al abrir, pulsar **Volver a cargar datos** en ese equipo. Pasa cuando el navegador guarda una copia de pedidos anterior a la instalación de las promociones.

## Promoción de inauguración

**Requisito:** un 10 % de descuento sobre el pedido, independiente de las listas de regalos, que el cajero decide aplicar en cada venta introduciendo un código.

Se resuelve con el programa estándar de promociones de Odoo, **sin código propio**. Es configuración guardada en la base de datos: no viaja con este repositorio y hay que crearla en cada entorno.

### Crear el programa

1. **Activar las promociones.** Punto de venta › Configuración › Ajustes. Marca "Promociones, cupones, tarjetas de regalo y programas de lealtad" y guarda. Esto instala módulos: hazlo con las cajas cerradas.
2. **Nuevo programa.** Punto de venta › Productos › Descuentos y programas de lealtad › Nuevo.
3. **Datos generales**
   - Nombre del programa: `Inauguración 10 %`
   - Tipo de programa: **Código de descuento**
   - Moneda: la misma de la caja; si no coincide, la caja no carga el programa
   - Fecha de inicio: `17/10/2026`
   - Fecha final: **pendiente de confirmar**
   - Límite de uso: sin marcar
   - Disponible en: solo **Punto de venta**
   - Punto de venta: la caja de Muebles
4. **Reglas condicionales.** Edita la regla que Odoo crea sola: código `INAUGURA10`, cantidad mínima `0`, compra mínima `0`.
5. **Recompensas.** Edita la recompensa que Odoo crea sola: Descuento, `10` %, aplicado sobre **Orden**. Odoo propone "Productos específicos"; si no se cambia, el descuento solo aplica a un producto.
6. Revisa la **descripción** de la recompensa (algo como "10% en su orden"): es el texto que sale en el ticket.
7. **Guardar.**

El día de inicio, abre o recarga la caja: los programas se cargan al abrirla, y una caja abierta desde el día anterior no reconocerá el código.

### Cómo se usa

En la caja: menú **⋮ › Ingresar código**, escribir `INAUGURA10` y pulsar Aplicar. Aparece una línea de descuento del 10 % en negativo. Sin el código no hay descuento.

En el entorno local se comprobó con dos ventas del mismo producto: con código, $ 1,950.00 quedó en $ 1,755.00; sin código, $ 1,950.00.

### Decisiones pendientes

- **Fecha de fin.** Sin ella el código vale indefinidamente.
- **Acumulación con otras promociones.** Lo que hace Odoo por defecto: solo admite un descuento "sobre la orden" por venta (si hay dos, aplica el mejor), pero sí lo suma a promociones de otro tipo: descuentos sobre productos concretos, "compra X y recibe Y", puntos de lealtad y pago con tarjeta de regalo. Si la respuesta es "no acumulable con nada", lo más simple es no tener otros programas activos en esa caja durante la promoción.

## Pendientes

- **Autorización del invitado.** Una casilla "el invitado autoriza que el dueño vea su nombre" y su uso en el correo de regalo recibido. Se evaluó y no se implementó.
- **Pantallas de oficina.** Se planteó rediseñar las vistas de Listas de regalos (tarjetas, formulario más claro, fotos en los productos). No se hizo.
- **Colores de marca.** El tema usa una paleta propuesta, no la identidad de Macromec. Cambiarla son unos pocos valores al inicio de `pos_theme.scss`.
- **Campo "Avance (%)".** Divide lo regalado entre lo deseado en total, así que un producto excedido compensa a otro pendiente y puede mostrar 100 % con cosas por regalar. Los avisos y la caja ya cuentan producto por producto.
- **Copias locales antiguas en la caja.** Se podría añadir una protección para que la caja tolere esas copias en vez de detenerse (ver [problemas conocidos](instalacion-y-comandos.md#problemas-conocidos)).
- **Portal web, traducción a `es_PE` y anonimización al cierre.** Estaban señalados como pendientes en el código base original y siguen así.

## Límites conocidos

- **Datos personales.** Se redujo la exposición dentro de Listas de regalos: datos enmascarados, enlace a la ficha solo para administradores y DNI con búsqueda exacta. Eso **no** impide que un cajero abra la aplicación Contactos, ni cambia que la caja estándar de Odoo le muestra el DNI, teléfono y correo de los clientes, que necesita para emitir comprobantes. Bloquear esos campos de verdad rompería la caja.
- **"Agotado".** Depende del stock del almacén de la caja. Odoo permite vender sin stock desde la pantalla normal; el diálogo de listas, no.
- **Aviso de eventos de hoy.** Su texto se fija a las 6:00 a. m. y no se actualiza si llegan regalos durante el día.
- **Horarios.** Las tareas "cerrar vencidas" y "recordatorio 7 días antes" usan la fecha UTC del servidor; el aviso diario usa la de Lima.
- **Fuentes del tema.** La caja descarga unos 900 KB de fuentes la primera vez; después quedan en la caché del navegador.
- **Nombres de producto.** La letra del tema es más ancha que la estándar y algunos nombres largos se cortan un poco antes.
