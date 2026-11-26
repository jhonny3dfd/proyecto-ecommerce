from django.urls import path
from . import views
from .views import LinkifyWebhookAPIView
from . import views_suscripciones as suscripciones
from . import views_cumpleanos as cumpleanos

# Todo lo que esté aquí, Django le pondrá '/api/configuracion/' antes
configuracion_urlpatterns = [
    # Ruta resultante: GET /api/configuracion/ (Pública)
    path('', views.ConfiguracionGlobalAPIView.as_view(), name='configuracion-global'),
    
    # Ruta resultante: GET/PATCH /api/configuracion/negocio/ (Administrador)
    path('negocio/', views.ConfiguracionNegocioView.as_view(), name='configuracion-negocio'),
]

# Todo lo que esté aquí, Django le pondrá '/api/ventas/' antes
ventas_urlpatterns = [
    # Couriers (RF-02.3): cotizar con los activos, sus comunas y sus sucursales
    # Ruta resultante: POST /api/ventas/logistica/cotizar/
    path('logistica/cotizar/', views.CotizacionEnvioView.as_view(), name='cotizar-envio'),
    path('logistica/comunas/', views.ComunasCoberturaAPIView.as_view(), name='comunas-cobertura'),
    path('logistica/sucursales/', views.SucursalesCourierAPIView.as_view(), name='sucursales-courier'),
    
    # Ruta resultante: POST /api/ventas/checkout/
    path('checkout/', views.CheckoutAPIView.as_view(), name='checkout'),
    path('checkout/verificar-pago/', views.VerificarEstadoPagoView.as_view(), name='verificar-pago'),
    path('promociones/', views.PromocionListCreateView.as_view(), name='promociones-list-create'),
    path('promociones/<int:pk>/', views.PromocionDetailView.as_view(), name='promociones-detail'),
    # NUEVA RUTA PARA EL RETORNO DE TRANSBANK
    # Ruta resultante: GET/POST /api/ventas/transbank/retorno/
    path('transbank/retorno/', views.TransbankRetornoView.as_view(), name='transbank_retorno'),
    # NUEVA RUTA PARA EL WEBHOOK DE MERCADOPAGO
    path('mercadopago/webhook/', views.MercadoPagoWebhookView.as_view(), name='mercadopago_webhook'),
    path('mercadopago/retorno/', views.MercadoPagoRetornoView.as_view(), name='mercadopago_retorno'),
    path('mercadopago/sincronizar/', views.AdminSincronizarPagosView.as_view(), name='mercadopago_sincronizar'),
    
    # Ruta resultante: GET /api/ventas/dashboard/
    path('dashboard/', views.DashboardOperativoView.as_view(), name='dashboard'),
    
    # --- NUEVA RUTA: MÉTRICAS DEL DASHBOARD ---
    # Ruta resultante: GET /api/ventas/dashboard/metricas/
    path('dashboard/metricas/', views.DashboardMetricasView.as_view(), name='dashboard_metricas'),
    path('dashboard/pendientes/', views.DashboardPendientesView.as_view(), name='dashboard_pendientes'),
    # Ruta resultante: GET /api/ventas/dashboard/exportar/ (Excel con las ventas del periodo)
    path('dashboard/exportar/', views.DashboardExportarVentasView.as_view(), name='dashboard_exportar'),
    
    path('checkout/reglas/', views.ReglasCheckoutView.as_view(), name='checkout-reglas'),

    path('tracking/', views.SeguimientoEnvioView.as_view(), name='tracking-envio'),
    
    # RUTA PARA EL CARRITO: GET/POST /api/ventas/carrito/
    path('carrito/', views.CarritoAPIView.as_view(), name='carrito-usuario'),
    # Ruta resultante: POST /api/ventas/carrito/validar/ (pública, también para invitados)
    path('carrito/validar/', views.ValidarCarritoView.as_view(), name='carrito-validar'),
    #para validar promociones
    path('promociones/validar/', views.ValidarPromocionAPIView.as_view(), name='validar-promocion'),
    # Descuentos automáticos vigentes, sin sus códigos: GET /api/ventas/promociones/automaticas/
    path('promociones/automaticas/', views.PromocionesAutomaticasAPIView.as_view(), name='promociones-automaticas'),
    
    path('mis-pedidos/', views.HistorialPedidosAPIView.as_view(), name='mis-pedidos'),
# --- RUTAS PARA DIRECCIONES DE ENVÍO ---
    # Ruta resultante: GET/POST /api/ventas/direcciones/
    path('direcciones/', views.DireccionEnvioListCreateView.as_view(), name='direcciones-list-create'),
    # Ruta resultante: GET/PUT/PATCH/DELETE /api/ventas/direcciones/<id>/
    path('direcciones/<int:pk>/', views.DireccionEnvioDetailView.as_view(), name='direcciones-detail'),
    # GET /api/ventas/empresa/: datos de facturación guardados del comprador (compra como empresa)
    path('empresa/', views.EmpresaCompradorView.as_view(), name='empresa-comprador'),
    # POST /api/ventas/cotizaciones/: formulario público de cotización y encargos
    path('cotizaciones/', views.CotizacionCreateView.as_view(), name='cotizaciones'),
    path('admin/cotizaciones/', views.AdminCotizacionListView.as_view(), name='admin-cotizaciones'),
    path('admin/cotizaciones/<int:pk>/', views.AdminCotizacionEstadoView.as_view(), name='admin-cotizacion-estado'),
    # Una foto que adjuntó el cliente: solo el admin (no está en /media/)
    path('admin/cotizaciones/<int:pk>/fotos/<int:foto_id>/', views.AdminFotoCotizacionView.as_view(),
         name='admin-foto-cotizacion'),
    # Reseñas (si el admin las activó): formulario con el enlace firmado del correo, envío y lo aprobado
    path('resenas/', views.ResenaEnvioView.as_view(), name='resenas'),
    path('resenas/formulario/', views.ResenaFormularioView.as_view(), name='resena-formulario'),
    path('resenas/tienda/', views.ResenasTiendaView.as_view(), name='resenas-tienda'),
    path('resenas/producto/<str:producto_id>/', views.ResenasProductoView.as_view(), name='resenas-producto'),
    # Panel: GET ?estado=&pagina= y PATCH {estado} para aprobar u ocultar
    path('admin/resenas/', views.AdminResenaListView.as_view(), name='admin-resenas'),
    path('admin/resenas/<int:pk>/', views.AdminResenaEstadoView.as_view(), name='admin-resena-estado'),
    
    # Ruta para descargar la etiqueta de la orden de transporte del courier
    path('ordenes/<int:orden_id>/etiqueta/', views.DescargarEtiquetaView.as_view(), name='descargar-etiqueta'),

    # NUEVAS RUTAS: administración de órdenes (solo administradores)
    # Ruta resultante: GET /api/ventas/admin/ordenes/
    path('admin/ordenes/', views.AdminOrdenCompraListView.as_view(), name='admin-ordenes-list'),
    # Ruta resultante: PATCH /api/ventas/admin/ordenes/<pk>/estado/
    path('admin/ordenes/<int:pk>/estado/', views.AdminOrdenCompraPatchView.as_view(), name='admin-ordenes-patch'),
    # Ruta resultante: POST /api/ventas/admin/ordenes/<pk>/revision/resolver/
    path('admin/ordenes/<int:pk>/revision/resolver/', views.AdminResolverRevisionView.as_view(),
         name='admin-ordenes-resolver-revision'),
    # Ruta resultante: POST /api/ventas/admin/ordenes/<pk>/orden-transporte/ (genera o reintenta la OT)
    path('admin/ordenes/<int:pk>/orden-transporte/', views.AdminOrdenTransporteView.as_view(),
         name='admin-ordenes-orden-transporte'),
    # POST { folio }: el folio de la boleta, factura o nota de crédito que la tienda emitió por su cuenta
    path('admin/ordenes/<int:pk>/documento/', views.AdminDocumentoOrdenView.as_view(), name='admin-ordenes-documento'),
    path('admin/ordenes/<int:pk>/pago-fuera-plazo/', views.AdminRegistrarPagoFueraPlazoView.as_view(),
        name='admin-ordenes-pago-fuera-plazo'),
    path('paginas-legales/', views.PaginaLegalListView.as_view(), name='paginas-legales-publicas'),
    # Ruta resultante: GET /api/ventas/paginas-legales/<tipo>/ (ej. terminos)
    path('paginas-legales/<str:tipo>/', views.PaginaLegalDetalleView.as_view(), name='pagina-legal-detalle'),
    # Rutas del editor del admin: GET la lista y PUT /api/ventas/admin/paginas-legales/<tipo>/
    path('admin/paginas-legales/', views.AdminPaginasLegalesView.as_view(), name='admin-paginas-legales'),
    path('admin/paginas-legales/<str:tipo>/', views.AdminPaginaLegalView.as_view(), name='admin-pagina-legal'),
    # Página independiente Sobre mí
    path('sobre-mi/', views.SobreMiPublicoView.as_view(), name='sobre-mi-publico'),
    path(
        'admin/sobre-mi/proyectos/',
        views.AdminSobreMiProyectosView.as_view(),
        name='admin-sobre-mi-proyectos',
    ),
    # Blog o portafolio (si el admin lo activó): GET /api/ventas/blog/?pagina=N y GET /api/ventas/blog/<slug>/
    path('blog/', views.BlogPublicoView.as_view(), name='blog'),
    path('blog/<slug:slug>/', views.BlogPublicacionView.as_view(), name='blog-publicacion'),
    # Panel: GET/POST publicaciones, GET/PUT/DELETE una, POST fotos (multipart) y DELETE una foto
    path('admin/blog/', views.AdminBlogView.as_view(), name='admin-blog'),
    path('admin/blog/<int:pk>/', views.AdminPublicacionView.as_view(), name='admin-blog-publicacion'),
    path('admin/blog/<int:pk>/fotos/', views.AdminFotosPublicacionView.as_view(), name='admin-blog-fotos'),
    path('admin/blog/<int:pk>/fotos/<int:foto_id>/', views.AdminFotoPublicacionView.as_view(),
         name='admin-blog-foto'),
    # Medios de pago (RN-02): GET la lista y PUT /api/ventas/admin/medios-pago/<codigo>/ (ej. transferencia)
    path('admin/medios-pago/', views.AdminMediosPagoView.as_view(), name='admin-medios-pago'),
    path('admin/medios-pago/<str:codigo>/', views.AdminMedioPagoView.as_view(), name='admin-medio-pago'),
    # Llaves de cada courier (RNF-03): GET enmascaradas y PUT para cargarlas o reemplazarlas
    path('admin/couriers/', views.AdminCouriersView.as_view(), name='admin-couriers'),
    path('admin/couriers/<str:codigo>/', views.AdminCourierView.as_view(), name='admin-courier'),
    # Suscripciones (pedido de un cliente, opcional): planes públicos y sus opciones, suscribirse, Mis suscripciones
    # (acciones y cambios) y pagar un pedido pendiente propio (el aviso de cobro de cada ciclo)
    path('suscripciones/planes/', suscripciones.PlanesPublicosView.as_view(), name='suscripciones-planes'),
    path('suscripciones/planes/<int:pk>/opciones/', suscripciones.OpcionesPlanView.as_view(),
         name='suscripciones-plan-opciones'),
    path('suscripciones/', suscripciones.SuscribirseView.as_view(), name='suscripciones'),
    path('suscripciones/mias/', suscripciones.MisSuscripcionesView.as_view(), name='suscripciones-mias'),
    path('suscripciones/beneficios/', suscripciones.BeneficiosView.as_view(), name='suscripciones-beneficios'),
    path('suscripciones/acceso-exclusivos/', suscripciones.AccesoExclusivosView.as_view(),
         name='suscripciones-acceso-exclusivos'),
    path('suscripciones/<int:pk>/', suscripciones.SuscripcionView.as_view(), name='suscripcion'),
    path('suscripciones/<int:pk>/<str:accion>/', suscripciones.AccionSuscripcionView.as_view(),
         name='suscripcion-accion'),
    path('mis-pedidos/<int:pk>/pagar/', suscripciones.PagarPedidoView.as_view(), name='pagar-pedido'),
    # Panel: planes (GET/POST, PUT/DELETE uno, PUT el orden) y suscriptores con filtros
    path('admin/suscripciones/planes/', suscripciones.AdminPlanesView.as_view(), name='admin-suscripciones-planes'),
    path('admin/suscripciones/planes/orden/', suscripciones.AdminOrdenPlanesView.as_view(),
         name='admin-suscripciones-planes-orden'),
    path('admin/suscripciones/planes/<int:pk>/', suscripciones.AdminPlanView.as_view(),
         name='admin-suscripciones-plan'),
    path('admin/suscripciones/', suscripciones.AdminSuscripcionesView.as_view(), name='admin-suscripciones'),
    path('admin/suscripciones/cumpleanos/', cumpleanos.AdminCumpleanosView.as_view(), name='admin-cumpleanos'),
    path('admin/suscripciones/cumpleanos/<int:usuario_id>/regalo/',
         cumpleanos.AdminRegaloCumpleanosView.as_view(), name='admin-regalo-cumpleanos'),
    # Ruta para las consultas y notificaciones de Linkify
    path('webhooks/linkify/', LinkifyWebhookAPIView.as_view(), name='webhook-linkify'),
]

urlpatterns = configuracion_urlpatterns + ventas_urlpatterns
