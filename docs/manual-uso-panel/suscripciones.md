# Suscripciones (manual de uso del panel)

Estos procedimientos están incluidos en el Word y el PDF del [manual de uso del panel](README.md). Las suscripciones son **opcionales y vienen apagadas**. Una tienda que no las active no ve ningún cambio.

## Qué son

El cliente recibe un producto cada cierto tiempo (por ejemplo, un café cada 4 semanas) sin tener que volver a comprarlo. Cada entrega es un **pedido normal**: aparece en Ventas, se prepara y se despacha como cualquier otro. Para suscribirse el cliente necesita una cuenta.

- Unos días antes de cada entrega (3 por defecto), la tienda crea el pedido y le envía al cliente un correo con el enlace para pagarlo.
- Si el cliente no lo paga hasta el final del día de la entrega, ese pedido se cancela solo y la suscripción sigue con la siguiente entrega.
- El cliente puede pausarla, reanudarla, saltar una entrega, recibir la próxima antes, cambiar el producto, la entrega o el medio de pago, y cancelarla, todo desde **Mi cuenta > Mis suscripciones**.
- En esta versión no se cobra automáticamente a la tarjeta: el cliente paga cada entrega con el enlace del correo, con Webpay, Mercado Pago o transferencia.

## Activarlas y crear los planes

Antes de activarlas, pide a tu equipo de apoyo que programe y compruebe la tarea diaria de suscripciones. Sin ella solo se genera el pedido inicial: no se crean las siguientes entregas ni se envían sus avisos de cobro. Esta preparación corresponde al equipo técnico; no se realiza desde el panel del emprendedor.

En **Configuración > Suscripciones**:

1. Cree al menos un plan con **+ Nuevo plan**:
   - **Nombre y descripción:** lo que ve el cliente en la página de suscripciones.
   - **Precio por entrega:** lo que paga el cliente en cada entrega, sin el despacho.
   - **Cada cuánto llega:** cada 1, 2, 3, 4, 6, 8 o 12 semanas.
   - **Unidades por entrega:** cuántas unidades del producto elegido recibe cada vez.
   - **Qué puede elegir el cliente:** categorías completas (también entran los productos que agregue después a esas categorías), productos sueltos o ambos. El cliente elige uno al suscribirse.
   - **Beneficios:** uno por línea, opcionales. El envío gratis y el descuento se agregan solos a la lista.
   - **Descuento en sus otras compras (%):** mientras la suscripción esté activa, el cliente lo recibe en todo lo que compre en la tienda con su cuenta.
   - **Envío gratis:** en las entregas de la suscripción y, si quiere, también en todas sus otras compras.
   - **Plan disponible:** si lo desmarca, el plan deja de mostrarse, pero quienes ya están suscritos siguen igual.
2. Marque **Ofrecer suscripciones en mi tienda** y guarde. Aparece "Suscripción" en el menú de la tienda y "Suscriptores" en el panel.
3. Si quiere, cambie los **días de anticipación** (de 1 a 14). Es también el plazo que tiene el cliente para pagar cada entrega.

Los botones **Subir** y **Bajar** cambian el orden de los planes en la tienda. Un plan con suscripciones no se puede borrar: desmárquelo como disponible.

## Atender a los suscriptores

- En **Suscriptores** está la lista con su estado, el plan, el producto, la próxima entrega y el pedido por pagar, si tiene uno. Se puede filtrar por estado y por plan, buscar por nombre, correo o producto, o ver solo a quienes tienen un pedido por pagar.
- En **Ventas**, los pedidos de una suscripción llevan la marca **"Suscripción"** con la fecha de la entrega. Se preparan y despachan como los demás.
- Si un cliente paga por transferencia, valide el pago en Ventas como siempre (Pendiente → Pagado). Con eso la suscripción avanza a la entrega siguiente.
- El aviso de cada próxima entrega incluye **Pagar esta entrega**. Si vence sin pago, se cancela ese ciclo y la suscripción continúa con el siguiente. Si nunca se paga la primera entrega, la suscripción no se activa y queda cancelada; el cliente recibe el aviso y puede suscribirse de nuevo.

## Productos exclusivos

Con las suscripciones activadas, en **Inventario > Agregar producto** o **Editar**:

1. Marque **Solo para suscriptores** en «Acceso de suscriptores».
2. Si quiere limitarlo a ciertos planes, márquelos. Sin seleccionar ninguno, cualquier plan vigente permite comprarlo.
3. Guarde el producto. En la tienda aparece **Exclusivo suscriptores**, con un enlace a Suscripción.

Para comprar por el carrito normal hace falta una suscripción activa y un plan permitido; una suscripción en espera del primer pago, pausada o cancelada no da ese acceso. Al contratar un plan nuevo sí se puede elegir su producto exclusivo desde el principio: la primera entrega queda pendiente hasta pagar. Un exclusivo reservado a otro plan sigue bloqueado. Los productos conservan sus reglas habituales de stock y publicación.

## Cumpleaños y regalos

- Con las suscripciones activadas en la tienda, el cliente puede registrar, cambiar o eliminar su día y mes desde **Mi cuenta > Mi cumpleaños**. Es opcional y no se pide el año de nacimiento.
- En **Cumpleaños del mes**, elija el mes. Se muestran los suscriptores activos con fecha registrada, su dirección o forma de entrega y su próxima entrega.
- Después de enviar el regalo, marque **Regalo enviado**. Queda registrado una vez por persona y año, aunque tenga varios planes; no puede volver a marcarlo durante ese año. El año siguiente tendrá un registro nuevo.
- Marcar la casilla solo registra el envío: no crea un pedido, un despacho ni un cobro, y no envía un correo automático de cumpleaños.

## Si las apaga

Al desmarcar **Ofrecer suscripciones en mi tienda**:

- La página de suscripciones deja de mostrarse.
- No se crean pedidos nuevos.
- Las suscripciones quedan guardadas, y los clientes todavía pueden verlas y cancelarlas desde su cuenta.
- Desaparecen la casilla de exclusividad y el listado de cumpleaños del panel. Los productos dejan de exigir una suscripción mientras el módulo esté apagado; al reactivarlo se recuperan sus restricciones guardadas.
