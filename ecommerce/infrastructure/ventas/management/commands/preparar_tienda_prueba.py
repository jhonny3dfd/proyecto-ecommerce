"""Datos iniciales de una tienda recién publicada.

Se puede correr las veces que haga falta: solo crea lo que falta y nunca pisa lo que el admin ya cambió.
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from ecommerce.application.medios_pago import ConfigurarMedioPago
from ecommerce.domain.medios_pago import AMBIENTE_INTEGRACION, CodigoMedioPago

from ...html_seguro import limpiar_html
from ...models import ConfiguracionGlobal, MedioPago, PaginaLegal
from ...repositorio_medios_pago import DjangoRepositorioMediosPago

# RN-02: Transbank en integración usa las llaves públicas de prueba, sin credenciales. Mercado Pago no va aquí:
# sus credenciales nunca van en el código, se cargan desde el panel
MEDIOS_DE_PRUEBA = {
    CodigoMedioPago.TRANSBANK: {'ambiente': AMBIENTE_INTEGRACION},
    # Datos claramente ficticios, para probar el flujo de la transferencia sin que nadie pague de verdad
    CodigoMedioPago.TRANSFERENCIA: {
        # El número tiene que ser de cuenta (domain/medios_pago.py): el aviso va en el banco, que también se ve
        'banco': 'Banco de PRUEBA, no transferir',
        'tipo_cuenta': 'Cuenta corriente',
        'numero_cuenta': '00000000',
        'rut_titular': '11.111.111-1',
        'nombre_titular': 'Tienda de prueba',
        'email': 'comprobantes@example.com',
    },
}

# Borradores: sin publicar Términos y Privacidad no se puede comprar (EXIGIR_PAGINAS_LEGALES), así que el
# admin tiene que completarlos con los datos reales de la tienda y publicarlos
AVISO_PLANTILLA = ('<p><strong>Plantilla de ejemplo:</strong> reemplaza cada [completar] con los datos de tu tienda. '
                   'Este texto no reemplaza la asesoría de un abogado: revísalo con uno antes de publicarlo.</p>')

PAGINAS_LEGALES = {
    'TERMINOS': ('Términos y Condiciones', AVISO_PLANTILLA + """
<h2>1. Quiénes somos</h2>
<p>[completar: nombre o razón social], RUT [completar], con domicilio en [completar], es la tienda que vende los
productos publicados en este sitio.</p>
<h2>2. Compras</h2>
<p>Los precios incluyen IVA y están expresados en pesos chilenos. El pedido se confirma cuando el pago es aprobado o,
en una transferencia, cuando la tienda la valida dentro del plazo informado al comprar.</p>
<h2>3. Despacho y retiro</h2>
<p>[completar: zonas de despacho, plazos y costos, y si existe retiro en el local].</p>
<h2>4. Cambios, devoluciones y derecho a retracto</h2>
<p>Se rigen por nuestra Política de Reembolsos y por la Ley N° 19.496 sobre Protección de los Derechos de los
Consumidores. [completar: condiciones de cambio].</p>
<h2>5. Contacto</h2>
<p>[completar: correo y teléfono de atención].</p>
"""),
    'PRIVACIDAD': ('Política de Privacidad', AVISO_PLANTILLA + """
<h2>1. Datos que recopilamos</h2>
<p>Nombre, correo, teléfono y dirección de despacho, para procesar y entregar los pedidos. Los datos de pago los
procesan Transbank o Mercado Pago; la tienda no guarda los datos de tu tarjeta.</p>
<h2>2. Para qué los usamos</h2>
<p>Para gestionar tu compra, enviarte los correos de seguimiento y atender tus consultas. [completar: otros usos,
como novedades o promociones, solo si das tu consentimiento].</p>
<h2>3. Con quién los compartimos</h2>
<p>Solo con quienes participan en la compra: el medio de pago y la empresa de despacho.</p>
<h2>4. Cookies</h2>
<p>Las cookies de analítica y marketing se activan solo si las aceptas en el aviso de cookies.</p>
<h2>5. Tus derechos</h2>
<p>Puedes pedir acceder, corregir o eliminar tus datos según la Ley N° 19.628, escribiendo a [completar: correo].</p>
"""),
    'REEMBOLSOS': ('Política de Reembolsos', AVISO_PLANTILLA + """
<h2>1. Derecho a retracto</h2>
<p>En las compras por internet puedes retractarte dentro de 10 días desde que recibes el producto, salvo las
excepciones de la Ley N° 19.496. [completar: si la tienda acepta o excluye el retracto, debe indicarlo aquí].</p>
<h2>2. Productos con falla</h2>
<p>[completar: plazo y forma de solicitar el cambio, la reparación o la devolución del dinero].</p>
<h2>3. Cómo se devuelve el dinero</h2>
<p>[completar: medio y plazo del reembolso].</p>
"""),
}


class Command(BaseCommand):
    help = ('Deja lista una tienda recién publicada: su configuración, Transbank en integración, una transferencia '
            'de prueba y los borradores de las páginas legales. Solo crea lo que falta: no pisa lo que el admin '
            'ya cambió. El administrador se crea aparte, con createsuperuser.')

    def add_arguments(self, parser):
        parser.add_argument('--nombre', required=True, help='Nombre de la tienda, ej. "Taller Maché".')

    @transaction.atomic
    def handle(self, *args, nombre, **options):
        self._configuracion(nombre.strip())
        self._medios_pago()
        self._paginas_legales()
        self.stdout.write('Siguiente paso: completar y publicar las páginas legales desde el panel, '
                          'porque sin Términos y Privacidad publicadas no se puede comprar.')

    def _configuracion(self, nombre):
        _, creada = ConfiguracionGlobal.objects.get_or_create(pk=1, defaults={
            'nombre_tienda': nombre,
            # El local de ejemplo no se publica: el admin carga su dirección y decide si ofrece el retiro
            'retiro_en_local_activo': False,
            'mostrar_direccion_pie': False,
        })
        self._informar(creada, f'Configuración de "{nombre}"', 'La configuración ya existía: no se cambió.')

    def _medios_pago(self):
        repositorio = DjangoRepositorioMediosPago()
        existentes = set(MedioPago.objects.values_list('codigo', flat=True))
        for codigo, datos in MEDIOS_DE_PRUEBA.items():
            nombre = repositorio.obtener(codigo).definicion.nombre
            if codigo.value in existentes:
                self.stdout.write(f'Medio de pago {nombre}: ya estaba configurado, no se cambió.')
                continue
            ConfigurarMedioPago(repositorio).ejecutar(codigo, True, datos)
            self.stdout.write(f'Medio de pago {nombre}: habilitado con datos de prueba.')

    def _paginas_legales(self):
        for tipo, (titulo, contenido) in PAGINAS_LEGALES.items():
            _, creada = PaginaLegal.objects.get_or_create(tipo_pagina=tipo, defaults={
                'titulo': titulo, 'contenido': limpiar_html(contenido), 'publicada': False,
            })
            self._informar(creada, f'{titulo} (borrador, sin publicar)', f'{titulo} ya existía: no se cambió.')

    def _informar(self, creada, texto_creada, texto_existente):
        self.stdout.write(f'{texto_creada}: creada.' if creada else texto_existente)
