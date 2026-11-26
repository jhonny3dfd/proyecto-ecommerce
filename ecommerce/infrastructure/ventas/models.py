from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.conf import settings

from ecommerce.domain.blog import (
    LARGO_NOMBRE_BLOG, LARGO_RESUMEN, LARGO_SLUG, LARGO_TITULO, NOMBRE_BLOG_POR_DEFECTO, EstadoPublicacion,
)
from ecommerce.domain.banner import (
    DESTINO_POR_DEFECTO, DESTINOS_BOTON, LARGO_ANTETITULO as LARGO_ANTETITULO_FOTO, LARGO_TEXTO as LARGO_TEXTO_FOTO,
    LARGO_TITULO as LARGO_TITULO_FOTO,
)
from ecommerce.domain.contacto import LOGO_UNIVERSIDAD_HEADER, UBICACIONES_LOGO_UNIVERSIDAD
from ecommerce.domain.cotizaciones import ETIQUETAS_ESTADO_COTIZACION, EstadoCotizacion
from ecommerce.domain.destacados import LARGO_TITULO as LARGO_TITULO_DESTACADOS
from ecommerce.domain.destacados import TITULO_POR_DEFECTO as TITULO_DESTACADOS, ModoVitrina
from ecommerce.domain.documentos_tributarios import ModeloEmision
from ecommerce.domain.medios_pago import MEDIOS_PAGO
from ecommerce.domain.resenas import (
    ESTRELLAS_MAXIMAS, ESTRELLAS_MINIMAS, ETIQUETAS_ESTADO_RESENA, LARGO_NOMBRE_PUBLICO, EstadoResena,
)
from ecommerce.domain.sobre_mi import LARGO_ALT_FOTO_SOBRE_MI
from ecommerce.domain.suscripciones import (
    DESCUENTO_MAXIMO, DIAS_AVISO_MAXIMO, DIAS_AVISO_MINIMO, DIAS_AVISO_POR_DEFECTO, ETIQUETAS_ESTADO_SUSCRIPCION,
    FRECUENCIA_MAXIMA_SEMANAS, FRECUENCIA_MINIMA_SEMANAS, LARGO_DESCRIPCION_PLAN, LARGO_NOMBRE_PLAN, PRECIO_MAXIMO,
    UNIDADES_MAXIMAS, EstadoSuscripcion,
)

class ConfiguracionGlobal(models.Model):
    MODOS_AUTENTICACION = [
        ('INVITADO', 'Invitado'),
        ('REGISTRO_OBLIGATORIO', 'Registro Obligatorio'),
        ('MIXTO', 'Mixto'),
    ]

    TIPOS_LAYOUT = [
        ('LISTA', 'Lista'),
        ('GRID_3', 'Cuadrícula de 3'),
        ('GRID_4', 'Cuadrícula de 4'),
    ]
    orden_catalogo = models.CharField(max_length=20, default='destacados', choices=[
        ('destacados', 'Orden actual'), ('recientes', 'Recientes primero'),
        ('precio-desc', 'Mayor precio'), ('precio-asc', 'Menor precio'),
    ])
    orden_categorias = models.JSONField(default=list, blank=True)
    menu_principal = models.JSONField(default=dict, blank=True)
    nombre_tienda = models.CharField(max_length=255)
    
    # --- CAMPOS DE ORIGEN / RETIRO EN LOCAL ---
    comuna_origen = models.CharField(
        max_length=100, 
        default='Santiago',
        help_text="Comuna desde donde se despachan los productos (Punto A)"
    )
    region_origen = models.CharField(
        max_length=100, 
        default='Metropolitana',
        blank=True, 
        null=True
    )
    calle_origen = models.CharField(max_length=255, default='Av. Principal', blank=True, null=True)
    numero_origen = models.CharField(max_length=50, default='123', blank=True, null=True)
    dpto_casa_origen = models.CharField(max_length=100, blank=True, null=True, help_text="Ej: Piso 4, Oficina 405 o Bodega B")
    retiro_en_local_activo = models.BooleanField(default=True, help_text="Permite a los clientes seleccionar retiro gratuito en local")
    # Entrega coordinada (RF-02.3): la tienda contacta al comprador para acordar la entrega, sin transportista
    entrega_coordinada_activa = models.BooleanField(default=False)
    costo_entrega_coordinada = models.PositiveIntegerField(default=0)
    instrucciones_entrega_coordinada = models.CharField(max_length=300, blank=True, default='')
    # Formulario de cotización y encargos (personalizados, a pedido o en cantidad): el admin lo activa
    cotizaciones_activas = models.BooleanField(default=False)
    # Suscripciones con entregas recurrentes (domain/suscripciones.py, pedido de un cliente): apagadas por defecto.
    # Días antes de cada entrega en que se crea el pedido del ciclo y se le pide el pago al cliente
    suscripciones_activas = models.BooleanField(default=False)
    suscripciones_dias_aviso = models.PositiveSmallIntegerField(
        default=DIAS_AVISO_POR_DEFECTO, validators=[MinValueValidator(DIAS_AVISO_MINIMO),
                                                    MaxValueValidator(DIAS_AVISO_MAXIMO)])
    # Blog o portafolio (domain/blog.py): activo, el enlace del menú lleva a /blog con el nombre que eligió el admin
    blog_activo = models.BooleanField(default=False)
    blog_nombre = models.CharField(max_length=LARGO_NOMBRE_BLOG, default=NOMBRE_BLOG_POR_DEFECTO)
    # Destacados de la landing (domain/destacados.py, pedido de un cliente): con DESTACADOS, la vitrina muestra los
    # productos y publicaciones que eligió el admin en vez de "Más vendidos". Por defecto queda como antes
    vitrina_modo = models.CharField(max_length=20, choices=[(modo.value, modo.value) for modo in ModoVitrina],
                                    default=ModoVitrina.MAS_VENDIDOS.value)
    destacados_titulo = models.CharField(max_length=LARGO_TITULO_DESTACADOS, default=TITULO_DESTACADOS)
    # [{'tipo': 'PRODUCTO' | 'PUBLICACION', 'id': '...'}] en orden. Los productos viven en MongoDB y las
    # publicaciones aquí, así que no hay clave foránea: lo borrado o despublicado se filtra al leer
    destacados = models.JSONField(default=list, blank=True)
    # Presentación de las fotos y del logo (pedido de un cliente, 2026-11-09). Apagadas, la tienda se ve como antes:
    # - fotos_completas: las fotos de productos se ven enteras dentro de su marco, sin recortarlas
    # - ficha_horizontal: la ficha del producto muestra la foto en un marco apaisado y más grande, con textos más chicos
    # - logo_grande: el logo del header se ve más grande en el computador (en el celular queda igual)
    video_banner_activo = models.BooleanField(default=False)
    fotos_completas = models.BooleanField(default=False)
    ficha_horizontal = models.BooleanField(default=False)
    logo_grande = models.BooleanField(default=False)
    # Página independiente "Sobre mí": desactivada por defecto.
    sobre_mi_activo = models.BooleanField(default=False)
    sobre_mi_nombre = models.CharField(max_length=30, default='Sobre mí')
    sobre_mi_biografia = models.TextField(blank=True, default='')
    # Hasta 2 fotos junto a la biografía (pedido de un cliente, opcionales), cada una con su texto alternativo
    sobre_mi_foto_1 = models.ImageField(upload_to='negocio/sobre_mi/', blank=True, null=True)
    sobre_mi_foto_1_alt = models.CharField(max_length=LARGO_ALT_FOTO_SOBRE_MI, blank=True, default='')
    sobre_mi_foto_2 = models.ImageField(upload_to='negocio/sobre_mi/', blank=True, null=True)
    sobre_mi_foto_2_alt = models.CharField(max_length=LARGO_ALT_FOTO_SOBRE_MI, blank=True, default='')
    # Reseñas con estrellas (domain/resenas.py): activas, el correo de entrega pide la reseña y la tienda la muestra
    resenas_activas = models.BooleanField(default=False)
    # El modelo de emisión que la tienda declaró en el SII (domain/documentos_tributarios.py): decide si un pago
    # con tarjeta también pide boleta en el panel. Sin declarar, el SII asume VOUCHER
    modelo_emision = models.CharField(max_length=20, choices=[(m.value, m.value) for m in ModeloEmision],
                                      default=ModeloEmision.VOUCHER.value)

    tema_seleccionado = models.IntegerField(default=1)
    # Combinación de fuentes (título + texto) de la tienda y el panel: los IDs y las fuentes viven en
    # frontend/src/constants/tipografias.js; 1 es la Editorial (Cormorant Garamond + Inter)
    tipografia_seleccionada = models.PositiveSmallIntegerField(
        default=1, validators=[MinValueValidator(1), MaxValueValidator(5)])
    logo =models.ImageField(upload_to='negocio/logos/', blank=True, null=True)
    favicon = models.ImageField(upload_to='negocio/favicons/', blank=True, null=True)
    google_analytics_id = models.CharField(max_length=50, blank=True, null=True)
    meta_pixel_id = models.CharField(max_length=50, blank=True, null=True)
    texto_bienvenida = models.TextField(
        default='Bienvenido a nuestra tienda',
    )
    texto_boton_ingreso = models.CharField(
        max_length=100,
        default='Ver Catálogo',
    )
    # Landing (RF-01.1): campos fijos que el admin edita desde el panel; el título es texto_bienvenida
    subtitulo_bienvenida = models.CharField(max_length=200, blank=True, default='')
    texto_landing = models.TextField(blank=True, default='')
    # Sección "Nosotros" de la landing: sin texto no se muestra
    nosotros_titulo = models.CharField(max_length=120, blank=True, default='')
    nosotros_texto = models.TextField(blank=True, default='')
    nosotros_imagen = models.ImageField(upload_to='negocio/nosotros/', blank=True, null=True)
    banner_url = models.URLField(max_length=500, blank=True, null=True)
    banner = models.ImageField(upload_to='negocio/banners/', blank=True, null=True)
    # Contacto y redes: van en el pie de página. La dirección es la del local (arriba) y solo se publica si
    # el admin lo elige o si hay retiro en local (domain/contacto.py)
    correo_contacto = models.EmailField(blank=True, default='')
    horario_atencion = models.TextField(blank=True, default='')
    mostrar_direccion_pie = models.BooleanField(default=False)
    # Teléfono comercial y redes sociales del emprendedor.
    # Todos son opcionales y no se muestran cuando están vacíos.
    telefono_comercial = models.CharField(max_length=20, blank=True, default='')
    facebook_url = models.URLField(max_length=500, blank=True, default='')
    x_url = models.URLField(max_length=500, blank=True, default='')
    youtube_url = models.URLField(max_length=500, blank=True, default='')
    tiktok_url = models.URLField(max_length=500, blank=True, default='')
    # RN-01: dónde va el logo de la Universidad, header o footer; nunca se oculta (domain/contacto.py)
    ubicacion_logo_universidad = models.CharField(
        max_length=10, choices=[(u, u) for u in UBICACIONES_LOGO_UNIVERSIDAD], default=LOGO_UNIVERSIDAD_HEADER)
    # Sección de Instagram de la landing: sin usuario no se muestra; las fotos las sube el admin (no es el feed)
    instagram_usuario = models.CharField(max_length=30, blank=True, default='')
    instagram_foto_1 = models.ImageField(upload_to='negocio/instagram/', blank=True, null=True)
    instagram_foto_2 = models.ImageField(upload_to='negocio/instagram/', blank=True, null=True)
    instagram_foto_3 = models.ImageField(upload_to='negocio/instagram/', blank=True, null=True)
    instagram_foto_4 = models.ImageField(upload_to='negocio/instagram/', blank=True, null=True)
    instagram_foto_5 = models.ImageField(upload_to='negocio/instagram/', blank=True, null=True)
    instagram_foto_6 = models.ImageField(upload_to='negocio/instagram/', blank=True, null=True)
    modo_autenticacion = models.CharField(
        max_length=25, 
        choices=MODOS_AUTENTICACION, 
        default='MIXTO'
    )
    
    layout_catalogo = models.CharField(max_length=50, choices=TIPOS_LAYOUT, default="GRID_3")

    def __str__(self):
        return self.nombre_tienda


class FotoBanner(models.Model):
    """Foto del carrusel de la portada (RF-01.1, SCRUM-194). Se ordenan con el campo orden."""

    configuracion = models.ForeignKey(ConfiguracionGlobal, on_delete=models.CASCADE, related_name='fotos_banner')
    imagen = models.ImageField(upload_to='negocio/banners/')
    video = models.FileField(upload_to='negocio/banners/videos/', blank=True, null=True)
    orden = models.PositiveSmallIntegerField(default=0)
    # Textos y botón propios de la foto (domain/banner.py): viajan con ella al reordenar
    antetitulo = models.CharField(max_length=LARGO_ANTETITULO_FOTO, blank=True, default='')
    titulo = models.CharField(max_length=LARGO_TITULO_FOTO, blank=True, default='')
    texto = models.TextField(max_length=LARGO_TEXTO_FOTO, blank=True, default='')
    destino = models.CharField(max_length=10, choices=[(destino, destino) for destino in DESTINOS_BOTON],
                               default=DESTINO_POR_DEFECTO)

    class Meta:
        ordering = ['orden', 'id']

    def __str__(self):
        return f'Foto banner {self.orden} de {self.configuracion}'


class MedioPago(models.Model):
    """Un medio de pago configurado por el emprendedor (RN-02). Los campos de cada medio los define el dominio."""

    codigo = models.CharField(max_length=30, unique=True,
                              choices=[(d.codigo.value, d.nombre) for d in MEDIOS_PAGO])
    habilitado = models.BooleanField(default=False)
    # Datos que no son secretos (ej. ambiente, datos bancarios que ve el comprador)
    datos = models.JSONField(default=dict, blank=True)
    # Credenciales en JSON cifrado con CLAVE_CIFRADO_CREDENCIALES; nunca en texto plano
    credenciales_cifradas = models.TextField(blank=True, default='')
    actualizado = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.get_codigo_display()


class ProveedorEnvio(models.Model):
    """Credenciales de un courier que carga el emprendedor en el panel, una fila por courier.

    El código es el del registro de couriers (ventas/couriers/__init__.py), ej. CHILEXPRESS.
    """

    codigo = models.CharField(max_length=30, unique=True)
    # JSON cifrado con CLAVE_CIFRADO_CREDENCIALES; nunca en texto plano
    credenciales_cifradas = models.TextField(blank=True, default='')
    actualizado = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.codigo


class DireccionEnvio(models.Model):
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='direcciones')
    calle = models.CharField(max_length=255)
    calle_numero = models.CharField(max_length=50)
    dpto_casa = models.CharField(max_length=100, blank=True, null=True)
    comuna = models.CharField(max_length=100)
    ciudad = models.CharField(max_length=100)
    # Opcional: el checkout no la pide y Chilexpress cotiza y despacha con la comuna
    region = models.CharField(max_length=100, blank=True, default='')
    codigo_postal = models.CharField(max_length=20, blank=True, null=True)
    es_predeterminado = models.BooleanField(default=False)

    def save(self, *args, **kwargs):
        # Si el usuario marca esta dirección como predeterminada,
        # desmarcamos las demás.
        if self.es_predeterminado:
            DireccionEnvio.objects.filter(usuario=self.usuario).update(es_predeterminado=False)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.calle} {self.calle_numero}, {self.ciudad}"

class EmpresaComprador(models.Model):
    """Datos de facturación que un comprador registrado guardó para sus próximas compras como empresa."""

    usuario = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='empresa')
    razon_social = models.CharField(max_length=150)
    rut = models.CharField(max_length=12)
    giro = models.CharField(max_length=120)
    direccion = models.CharField(max_length=255)
    correo = models.EmailField()

    def __str__(self):
        return f'{self.razon_social} ({self.rut})'


class Cotizacion(models.Model):
    """Solicitud de cotización o encargo de una persona o empresa (domain/cotizaciones.py)."""

    ESTADOS = [(estado.value, etiqueta) for estado, etiqueta in ETIQUETAS_ESTADO_COTIZACION.items()]

    fecha_creacion = models.DateTimeField(auto_now_add=True)
    estado = models.CharField(max_length=20, choices=ESTADOS, default=EstadoCotizacion.NUEVA.value)
    nombre = models.CharField(max_length=120)
    correo = models.EmailField()
    telefono = models.CharField(max_length=15)
    # Del catálogo (id de MongoDB y nombre al cotizar) o descrito por el cliente
    producto_id = models.CharField(max_length=24, blank=True, default='')
    producto_nombre = models.CharField(max_length=255, blank=True, default='')
    descripcion = models.TextField(blank=True, default='')
    cantidad = models.PositiveIntegerField()
    personalizacion = models.TextField(blank=True, default='')
    fecha_requerida = models.DateField(null=True, blank=True)
    # Cotiza como empresa: los datos para la factura (null si es una persona)
    datos_empresa = models.JSONField(null=True, blank=True)

    class Meta:
        ordering = ['-fecha_creacion', '-id']

    def __str__(self):
        return f'Cotización #{self.id} - {self.nombre}'


class FotoCotizacion(models.Model):
    """Foto de la idea del cliente. El archivo está en ARCHIVOS_PRIVADOS_ROOT, no en media: solo lo entrega la API
    al admin (repositorio_cotizaciones.py)."""

    cotizacion = models.ForeignKey(Cotizacion, on_delete=models.CASCADE, related_name='fotos')
    # Ruta relativa dentro de ARCHIVOS_PRIVADOS_ROOT, con un nombre al azar
    ruta = models.CharField(max_length=255)

    class Meta:
        ordering = ['id']


class Promocion(models.Model):
    TIPOS_DESCUENTO = [
        ('PORCENTAJE', 'Porcentaje (%)'),
        ('MONTO_FIJO', 'Monto Fijo'),
    ]

    codigo = models.CharField(max_length=50, unique=True)
    tipo_descuento = models.CharField(max_length=20, choices=TIPOS_DESCUENTO)
    valor_descuento = models.FloatField()
    umbral_envio_gratis = models.FloatField(null=True, blank=True)
    fecha_expiracion = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    # Desde qué subtotal vale (vacío = cualquier compra); uno automático lo exige (domain/promociones.py)
    monto_minimo = models.PositiveIntegerField(null=True, blank=True)
    # Se aplica solo, sin escribir el código, a toda compra desde monto_minimo
    automatica = models.BooleanField(default=False)
    # Cuántas compras pueden usarlo (vacío = sin límite) y cuántas lo usaron; el checkout suma el uso de forma
    # atómica (reservar_uso_promocion), así dos compras simultáneas no se pasan del límite
    usos_maximos = models.PositiveIntegerField(null=True, blank=True)
    usos = models.PositiveIntegerField(default=0)

    @property
    def esta_vigente(self) -> bool:
        from django.utils import timezone
        if not self.is_active:
            return False
        if self.fecha_expiracion and self.fecha_expiracion < timezone.now():
            return False
        if self.usos_maximos is not None and self.usos >= self.usos_maximos:
            return False
        return True

    def __str__(self):
        estado = "Activa" if self.esta_vigente else "Inactiva/Expirada"
        return f"{self.codigo} ({estado})"

class OrdenCompra(models.Model):
    ESTADOS_PEDIDO = [
        ('PENDIENTE', 'Pendiente'),
        ('PAGADO', 'Pagado'),
        ('EN_PREPARACION', 'En preparación'),
        ('ENVIADO', 'Enviado'),
        ('ENTREGADO', 'Entregado'),
        ('CANCELADO', 'Cancelado'),
    ]
    
    METODOS_PAGO = [
        ('TRANSBANK', 'Transbank'),
        ('PAYPAL', 'PayPal'),
        ('LINKIFY', 'Linkify'),
        ('MERCADO_PAGO', 'Mercado Pago'),
        ('TRANSFERENCIA', 'Transferencia'),
    ]

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='ordenes'
    )
    email_invitado = models.CharField(max_length=255, blank=True, null=True)
    promocion = models.ForeignKey(Promocion, on_delete=models.SET_NULL, null=True, blank=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    estado = models.CharField(max_length=50, choices=ESTADOS_PEDIDO, default='PENDIENTE')
    metodo_pago = models.CharField(max_length=50, choices=METODOS_PAGO)
    direccion_envio_snapshot = models.JSONField()
    # Compra como empresa: razón social, RUT, giro, dirección y correo para la factura, tal como venían al
    # comprar (domain/empresa.py). Vacío si compra una persona
    datos_empresa = models.JSONField(null=True, blank=True)
    # Quién recibe o retira el pedido (RF-02.3); la orden de transporte usa estos datos
    nombre_destinatario = models.CharField(max_length=120, blank=True, default='')
    # Normalizado como +56XXXXXXXXX (normalizar_telefono_chile)
    telefono_destinatario = models.CharField(max_length=15, blank=True, default='')

    id_transaccion_pasarela = models.CharField(max_length=255, blank=True, null=True)
    proveedor_logistico = models.CharField(max_length=100, blank=True, null=True)
    numero_seguimiento_tracking = models.CharField(max_length=100, blank=True, null=True)
    # Peso y medidas cotizados en el checkout; la orden de transporte usa los mismos
    paquete = models.JSONField(null=True, blank=True)
    # Último error del transportista al generar la OT (vacío si se generó o no aplica)
    error_orden_transporte = models.CharField(max_length=255, blank=True, default='')

    subtotal = models.FloatField()
    costo_envio = models.FloatField()
    total_final = models.FloatField()

    # El admin debe revisar la orden (ej. pago confirmado sin stock); el estado no cambia
    requiere_revision = models.BooleanField(default=False)
    motivo_revision = models.CharField(max_length=255, blank=True, default='')
    motivo_cancelacion = models.CharField(max_length=255, blank=True, default='')
    # Al cancelar solo se repone el stock que realmente se descontó
    stock_descontado = models.BooleanField(default=False)
    # Transferencia: plazo de pago que tenía la tienda al crear la orden (domain/ventas.py: plazo_pago); un
    # cambio de plazo posterior no lo altera. Vacíos en los demás medios de pago
    fecha_limite_pago = models.DateTimeField(null=True, blank=True)
    fecha_recordatorio_pago = models.DateTimeField(null=True, blank=True)
    # Transferencia: ya se le recordó al comprador el pago, a la mitad del plazo (se envía una sola vez)
    recordatorio_pago_enviado = models.BooleanField(default=False)
    # Cuándo pasó a Entregado; desde ahí corre el plazo para dejar la reseña. Vacío en los entregados antes de
    # que se registrara
    fecha_entrega = models.DateTimeField(null=True, blank=True)
    # Cuándo pasó a Pagado (pago en línea confirmado o transferencia validada): el dashboard cuenta las ventas por
    # esta fecha. En los pagados antes de que se registrara se rellenó con la de creación
    fecha_pago = models.DateTimeField(null=True, blank=True)
    # Folios que la tienda anota de los documentos que emitió por su cuenta (domain/documentos_tributarios.py):
    # la boleta o factura del pedido y, si se canceló después, su nota de crédito
    folio_documento = models.CharField(max_length=10, blank=True, default='')
    folio_nota_credito = models.CharField(max_length=10, blank=True, default='')
    # Pedido de un ciclo de una suscripción (domain/suscripciones.py): la fecha es la de la entrega del ciclo. Un
    # ciclo tiene un solo pedido. Vacíos en las compras normales
    suscripcion = models.ForeignKey('Suscripcion', on_delete=models.PROTECT, null=True, blank=True,
                                    related_name='pedidos')
    ciclo_fecha = models.DateField(null=True, blank=True)

    class Meta:
        constraints = [
            # Ni un pago repetido ni dos ejecuciones de la tarea diaria crean dos pedidos del mismo ciclo. Un ciclo
            # cancelado (no pagado o saltado) libera su fecha
            models.UniqueConstraint(
                fields=['suscripcion', 'ciclo_fecha'], name='orden_un_pedido_por_ciclo',
                condition=models.Q(suscripcion__isnull=False) & ~models.Q(estado='CANCELADO')),
        ]

    def __str__(self):
        identificador = self.email_invitado if self.email_invitado else self.usuario
        return f"Orden #{self.id} - {identificador}"

class DetalleOrden(models.Model):
    orden = models.ForeignKey(OrdenCompra, on_delete=models.CASCADE, related_name='detalles')
    producto_mongo_id = models.CharField(max_length=255)
    variante_sku = models.CharField(max_length=255)
    nombre_producto_snapshot = models.CharField(max_length=255)
    precio_unitario_snapshot = models.FloatField() 
    cantidad = models.IntegerField()

    def __str__(self):
        return f"{self.cantidad}x {self.nombre_producto_snapshot} (Orden #{self.orden.id})"

class PaginaLegal(models.Model):
    TIPOS_PAGINA = [
        ('TERMINOS', 'Términos y Condiciones'),
        ('PRIVACIDAD', 'Política de Privacidad'),
        ('REEMBOLSOS', 'Política de Reembolsos'),
    ]

    tipo_pagina = models.CharField(max_length=30, choices=TIPOS_PAGINA, unique=True)
    titulo = models.CharField(max_length=255)
    # HTML del editor, ya limpio (html_seguro.limpiar_html) al guardarse
    contenido = models.TextField()
    # RF-03.5: solo las publicadas aparecen en el footer y son visibles al público
    publicada = models.BooleanField(default=False)
    ultima_actualizacion = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.get_tipo_pagina_display()} - {self.titulo}"


class Publicacion(models.Model):
    """Entrada del blog o portafolio de la tienda (domain/blog.py, application/blog.py)."""

    ESTADOS = [(EstadoPublicacion.BORRADOR.value, 'Borrador'), (EstadoPublicacion.PUBLICADA.value, 'Publicada')]

    titulo = models.CharField(max_length=LARGO_TITULO)
    # Con espacio para el sufijo de los títulos repetidos (-2, -3...)
    slug = models.SlugField(max_length=LARGO_SLUG + 10, unique=True)
    resumen = models.CharField(max_length=LARGO_RESUMEN, blank=True, default='')
    # HTML del editor, ya limpio (html_seguro.limpiar_html) al guardarse
    contenido = models.TextField(blank=True, default='')
    portada = models.ImageField(upload_to='blog/portadas/', blank=True, null=True)
    youtube_id = models.CharField(max_length=20, blank=True, default='')
    estado = models.CharField(max_length=20, choices=ESTADOS, default=EstadoPublicacion.BORRADOR.value)
    # Se fija la primera vez que se publica y ordena el blog; None si nunca salió de borrador
    fecha_publicacion = models.DateTimeField(null=True, blank=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    actualizada = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-fecha_publicacion', '-id']
        indexes = [models.Index(fields=['estado', '-fecha_publicacion'], name='publicacion_estado_fecha')]

    def __str__(self):
        return self.titulo


class FotoPublicacion(models.Model):
    """Foto de la galería de una publicación (hasta MAX_FOTOS_PUBLICACION)."""

    publicacion = models.ForeignKey(Publicacion, on_delete=models.CASCADE, related_name='fotos')
    imagen = models.ImageField(upload_to='blog/fotos/')
    orden = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ['orden', 'id']

    def __str__(self):
        return f'Foto {self.orden} de {self.publicacion}'

class ProyectoDestacadoSobreMi(models.Model):
    """Publicación del blog seleccionada para la página Sobre mí."""

    configuracion = models.ForeignKey(
        ConfiguracionGlobal,
        on_delete=models.CASCADE,
        related_name='proyectos_sobre_mi'
    )
    publicacion = models.ForeignKey(
        Publicacion,
        on_delete=models.CASCADE,
        related_name='selecciones_sobre_mi'
    )
    orden = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['orden', 'id']
        constraints = [
            models.UniqueConstraint(
                fields=['configuracion', 'publicacion'],
                name='proyecto_sobre_mi_unico'
            )
        ]

    def __str__(self):
        return f'{self.publicacion.titulo} (orden {self.orden})'

def _estrellas_validas(prefijo):
    return models.CheckConstraint(
        condition=models.Q(estrellas__gte=ESTRELLAS_MINIMAS, estrellas__lte=ESTRELLAS_MAXIMAS),
        name=f'{prefijo}_estrellas_validas')


class Resena(models.Model):
    """Reseña de un pedido entregado, una por pedido (domain/resenas.py). Solo las aprobadas se publican.

    No se registra en el admin de Django: el admin de la tienda solo aprueba u oculta desde el panel.
    """

    ESTADOS = [(estado.value, etiqueta) for estado, etiqueta in ETIQUETAS_ESTADO_RESENA.items()]

    orden = models.OneToOneField(OrdenCompra, on_delete=models.CASCADE, related_name='resena')
    estado = models.CharField(max_length=20, choices=ESTADOS, default=EstadoResena.PENDIENTE.value)
    # De la tienda (obligatorias)
    estrellas = models.PositiveSmallIntegerField()
    comentario = models.TextField(blank=True, default='')
    nombre_publico = models.CharField(max_length=LARGO_NOMBRE_PUBLICO)
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-fecha_creacion', '-id']
        indexes = [models.Index(fields=['estado', '-fecha_creacion'], name='resena_estado_fecha')]
        constraints = [_estrellas_validas('resena')]

    def __str__(self):
        return f'Reseña del pedido #{self.orden_id} ({self.estrellas} estrellas)'


class ResenaProducto(models.Model):
    """Calificación de un producto del pedido dentro de una reseña; se aprueba u oculta junto con ella."""

    resena = models.ForeignKey(Resena, on_delete=models.CASCADE, related_name='productos')
    # Id de MongoDB, como DetalleOrden: la reseña no escribe en el catálogo
    producto_mongo_id = models.CharField(max_length=255)
    # Copiado del pedido
    producto_nombre = models.CharField(max_length=255)
    estrellas = models.PositiveSmallIntegerField()
    comentario = models.TextField(blank=True, default='')

    class Meta:
        ordering = ['id']
        indexes = [models.Index(fields=['producto_mongo_id'], name='resena_producto_id')]
        constraints = [
            _estrellas_validas('resena_producto'),
            models.UniqueConstraint(fields=['resena', 'producto_mongo_id'], name='resena_producto_unico'),
        ]

    def __str__(self):
        return f'{self.producto_nombre}: {self.estrellas} estrellas'

class Carrito(models.Model):
    # Relación 1 a 1: Cada usuario tiene exactamente un carrito
    usuario = models.OneToOneField(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='carrito'
    )
    # Aquí guardaremos el array de productos exactamente como lo maneja React
    items = models.JSONField(default=list, blank=True) 

    def __str__(self):
        return f"Carrito de {self.usuario.email}"

class PlanSuscripcion(models.Model):
    """Plan de suscripción que ofrece la tienda (domain/suscripciones.py: DatosPlan valida los datos)."""

    nombre = models.CharField(max_length=LARGO_NOMBRE_PLAN)
    descripcion = models.CharField(max_length=LARGO_DESCRIPCION_PLAN, blank=True, default='')
    # Pesos enteros por ciclo, por las unidades de la variante que elija el cliente
    precio = models.PositiveIntegerField(validators=[MinValueValidator(1), MaxValueValidator(PRECIO_MAXIMO)])
    frecuencia_semanas = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(FRECUENCIA_MINIMA_SEMANAS), MaxValueValidator(FRECUENCIA_MAXIMA_SEMANAS)])
    unidades = models.PositiveSmallIntegerField(default=1, validators=[MinValueValidator(1),
                                                                       MaxValueValidator(UNIDADES_MAXIMAS)])
    beneficios = models.JSONField(default=list, blank=True)
    # Qué puede elegir el cliente: productos de estas categorías y estos productos (ids de MongoDB)
    categorias = models.JSONField(default=list, blank=True)
    productos = models.JSONField(default=list, blank=True)
    envio_gratis = models.BooleanField(default=False)
    # Además, el suscriptor no paga despacho en ninguna de sus compras (exige envio_gratis)
    envio_gratis_compras = models.BooleanField(default=False)
    # Porcentaje de descuento en las compras del suscriptor mientras su suscripción esté activa
    descuento = models.PositiveSmallIntegerField(default=0, validators=[MaxValueValidator(DESCUENTO_MAXIMO)])
    activo = models.BooleanField(default=True)
    orden = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ['orden', 'id']

    def __str__(self):
        return self.nombre


class Suscripcion(models.Model):
    """Suscripción de un cliente a un plan: cada ciclo es un pedido (OrdenCompra.suscripcion)."""

    ESTADOS = [(estado.value, ETIQUETAS_ESTADO_SUSCRIPCION[estado]) for estado in EstadoSuscripcion]

    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='suscripciones')
    # Un plan con suscripciones no se borra: se desactiva
    plan = models.ForeignKey(PlanSuscripcion, on_delete=models.PROTECT, related_name='suscripciones')
    estado = models.CharField(max_length=20, choices=ESTADOS, default=EstadoSuscripcion.PENDIENTE.value)
    # Lo que recibe en cada entrega: una variante de un producto elegible del plan
    producto_mongo_id = models.CharField(max_length=255)
    variante_sku = models.CharField(max_length=255)
    nombre_producto = models.CharField(max_length=255)
    # Adónde y cómo se entrega, con el mismo formato que el pedido (OrdenCompra.direccion_envio_snapshot)
    direccion_envio = models.JSONField(default=dict, blank=True)
    nombre_destinatario = models.CharField(max_length=150, blank=True, default='')
    telefono_destinatario = models.CharField(max_length=15, blank=True, default='')
    proveedor_logistico = models.CharField(max_length=50)
    metodo_pago = models.CharField(max_length=50)
    # Fecha de entrega del próximo ciclo; vacía hasta el primer pago
    proxima_entrega = models.DateField(null=True, blank=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_activacion = models.DateTimeField(null=True, blank=True)
    fecha_cancelacion = models.DateTimeField(null=True, blank=True)
    motivo_cancelacion = models.CharField(max_length=255, blank=True, default='')

    class Meta:
        ordering = ['-fecha_creacion']
        indexes = [models.Index(fields=['estado', 'proxima_entrega'], name='suscripcion_estado_proxima')]

    def __str__(self):
        return f'Suscripción #{self.id} de {self.usuario} al plan {self.plan}'


class RegaloCumpleanos(models.Model):
    """Un regalo anual por persona, aunque tenga varias suscripciones o cambie de plan."""
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='regalos_cumpleanos')
    anio = models.PositiveSmallIntegerField()
    fecha_envio = models.DateTimeField(auto_now_add=True)
    enviado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
                                    related_name='+')

    class Meta:
        constraints = [models.UniqueConstraint(fields=['usuario', 'anio'], name='regalo_cumpleanos_usuario_anio')]
