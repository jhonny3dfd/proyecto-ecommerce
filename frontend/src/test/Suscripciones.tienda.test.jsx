import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom';

const { configuracion } = vi.hoisted(() => ({ configuracion: { actual: null } }));

vi.mock('../components/auth/axiosConfig', () => ({ default: { get: vi.fn(), post: vi.fn(), patch: vi.fn() } }));
vi.mock('../hooks/useConfiguracionTienda', () => ({
  default: () => configuracion.actual,
  recargarConfiguracion: vi.fn()
}));

import clienteAxios from '../components/auth/axiosConfig';
import Suscripcion from '../pages/Suscripcion';
import SuscribirsePlan from '../pages/SuscribirsePlan';
import MisSuscripciones from '../pages/MisSuscripciones';
import PagarEntrega from '../pages/PagarEntrega';
import MenuUsuario from '../components/MenuUsuario';
import { beneficiosDelPlan, descuentoSuscriptor, fechaEnDias, fechaLarga, textoVariante } from '../utils/suscripciones';
import { entregaParaServidor, faltaEnEntrega } from '../utils/entregaSuscripcion';

// Suscripciones (pedido de un cliente, opcional): la tienda

const PLAN = {
  id: 1, nombre: 'Café del mes', descripcion: 'Recién tostado', precio: 14990, frecuencia_semanas: 4,
  frecuencia_texto: 'Cada 4 semanas', unidades: 1, beneficios: ['Guía de preparación'], envio_gratis: true,
  envio_gratis_compras: false, descuento: 10
};

const PRODUCTOS = [
  { id: 'p1', nombre: 'Bourbon Rosado', categoria: 'Cafés', imagen: null, variantes: [
    { sku: 'BR-GRANO', atributos: { molienda: 'Grano' }, disponible: true },
    { sku: 'BR-MOLIDO', atributos: { molienda: 'Molido' }, disponible: false }
  ] },
  { id: 'p2', nombre: 'Agotado', categoria: 'Cafés', imagen: null, variantes: [
    { sku: 'AG-1', atributos: {}, disponible: false }
  ] }
];

const CONFIG = {
  nombre_tienda: 'Lumière', suscripciones_activas: true, couriers: [], retiro_en_local_activo: true,
  entrega_coordinada_activa: true, costo_entrega_coordinada: 3000, calle_origen: 'Av. Providencia',
  numero_origen: '2246', comuna_origen: 'Providencia', pasarelas_activas: ['TRANSBANK', 'TRANSFERENCIA']
};

const suscripcion = (cambios = {}) => ({
  id: 4, plan: PLAN, estado: 'ACTIVA', estado_texto: 'Activa', producto_mongo_id: 'p1', variante_sku: 'BR-GRANO',
  producto: 'Bourbon Rosado - Grano', entrega: { proveedor_logistico: 'RETIRO_LOCAL', direccion_envio_snapshot: {},
    nombre_destinatario: 'Ana Pérez', telefono_destinatario: '+56912345678', texto: 'Retiro en el local' },
  metodo_pago: 'TRANSBANK', proxima_entrega: '2026-12-12', fecha_creacion: '2026-11-11T12:00:00Z',
  pedido_pendiente: null, acciones: ['PAUSAR', 'SALTAR', 'ADELANTAR', 'CANCELAR', 'CAMBIAR'], ...cambios
});

// Muestra dónde terminó la navegación y con qué datos
function Destino() {
  const ubicacion = useLocation();
  return <p data-testid="destino">{ubicacion.pathname}{ubicacion.search} {JSON.stringify(ubicacion.state)}</p>;
}

function montar(ruta, elemento, patron) {
  return render(
    <MemoryRouter initialEntries={[ruta]}>
      <Routes>
        <Route path={patron} element={elemento} />
        <Route path="*" element={<Destino />} />
      </Routes>
    </MemoryRouter>
  );
}

const respuestas = (mapa) => clienteAxios.get.mockImplementation((url) => {
  if (url in mapa) {
    const valor = mapa[url];
    return valor instanceof Error ? Promise.reject(valor) : Promise.resolve({ data: valor });
  }
  return Promise.resolve({ data: [] });
});

const error404 = () => Object.assign(new Error('404'), { response: { status: 404 } });

beforeEach(() => {
  vi.clearAllMocks();
  localStorage.clear();
  configuracion.actual = CONFIG;
});

afterEach(() => cleanup());

describe('utilidades de suscripciones', () => {
  it('calculan descuento, textos y fechas como el servidor', () => {
    expect(descuentoSuscriptor(20000, 10)).toBe(2000);
    expect(descuentoSuscriptor(500, 90)).toBe(450);
    expect(descuentoSuscriptor(1000, 0)).toBe(0);
    expect(fechaLarga('2026-11-14')).toBe('14 de noviembre de 2026');
    expect(fechaEnDias(3, new Date(2026, 10, 30))).toBe('2026-12-03');
    expect(textoVariante({ molienda: 'Grano', peso: '250 g' })).toBe('Molienda: Grano · Peso: 250 g');
    expect(beneficiosDelPlan(PLAN)).toEqual(['Guía de preparación', 'Envío gratis en tus entregas',
      '10% de descuento en todas tus compras en la tienda']);
  });

  it('la entrega pide quién recibe y, a domicilio, la dirección y la cotización', () => {
    const base = { tipo: 'DOMICILIO', proveedor: '', direccionId: 'nueva', nombre: 'Ana', telefono: '+569',
      direccion: { calle: 'Los Aromos', numero: '', dpto_casa: '', comuna: 'Ñuñoa', ciudad: '' } };
    expect(faltaEnEntrega(base, [], null)).toBe('Completa la calle, el número y la comuna.');
    const completa = { ...base, direccion: { ...base.direccion, numero: '1550' } };
    expect(faltaEnEntrega(completa, [], { cargando: true })).toBe('Calculando el despacho...');
    const cotizacion = { opcion: { proveedor: 'CHILEXPRESS', precio: 3990 } };
    expect(faltaEnEntrega(completa, [], cotizacion)).toBe('');
    expect(faltaEnEntrega({ ...completa, telefono: ' ' }, [], cotizacion)).toBe('Indica el nombre y el teléfono de quien recibe.');
    expect(entregaParaServidor(completa, [], cotizacion)).toEqual({
      proveedor_logistico: 'CHILEXPRESS', nombre_destinatario: 'Ana', telefono_destinatario: '+569',
      direccion_envio_snapshot: { calle: 'Los Aromos', numero: '1550', comuna: 'Ñuñoa' }
    });
    expect(entregaParaServidor({ ...completa, tipo: 'RETIRO_LOCAL' }, [], null).direccion_envio_snapshot).toEqual({});
  });
});

describe('Página de planes (/suscripcion)', () => {
  it('muestra cada plan con su precio, frecuencia y beneficios', async () => {
    respuestas({ 'ventas/suscripciones/planes/': { planes: [PLAN], dias_aviso: 3 } });
    montar('/suscripcion', <Suscripcion />, '/suscripcion');

    const plan = (await screen.findByRole('heading', { name: 'Café del mes' })).closest('article');
    expect(within(plan).getByText('$14.990')).toBeInTheDocument();
    expect(within(plan).getByText(/Cada 4 semanas · 1 unidad/)).toBeInTheDocument();
    expect(within(plan).getByText('10% de descuento en todas tus compras en la tienda')).toBeInTheDocument();
    expect(within(plan).getByRole('link', { name: 'Suscribirme a Café del mes' })).toHaveAttribute('href', '/suscripcion/1');
    expect(screen.getByText(/3 días antes de cada entrega/)).toBeInTheDocument();
  });

  it('con el módulo apagado avisa que no está disponible', async () => {
    respuestas({ 'ventas/suscripciones/planes/': error404() });
    montar('/suscripcion', <Suscripcion />, '/suscripcion');

    expect(await screen.findByText(/no ofrece suscripciones por ahora/)).toBeInTheDocument();
    expect(screen.queryByRole('link', { name: /Suscribirme/ })).not.toBeInTheDocument();
  });
});

describe('Suscribirse a un plan (/suscripcion/:planId)', () => {
  const planYOpciones = {
    'ventas/suscripciones/planes/': { planes: [PLAN], dias_aviso: 3 },
    'ventas/suscripciones/planes/1/opciones/': { productos: PRODUCTOS },
    'usuarios/me/': { nombre: 'Ana', apellido_paterno: 'Pérez', telefono: '+56912345678' },
    'ventas/direcciones/': [],
    'ventas/paginas-legales/': [{ tipo_pagina: 'TERMINOS' }]
  };

  it('sin sesión pide iniciar sesión y vuelve a esta página', async () => {
    respuestas(planYOpciones);
    montar('/suscripcion/1', <SuscribirsePlan />, '/suscripcion/:planId');

    fireEvent.click(await screen.findByRole('button', { name: 'Iniciar sesión o crear cuenta' }));
    expect(localStorage.getItem('url_anterior_login')).toBe('/');
    expect(screen.getByTestId('destino')).toHaveTextContent('/login');
  });

  it('no deja suscribirse sin elegir producto ni aceptar los términos (RF-04.4), y envía lo elegido', async () => {
    localStorage.setItem('access_token', 'token');
    respuestas(planYOpciones);
    clienteAxios.post.mockResolvedValue({ data: { suscripcion_id: 4, orden_id: 81, total: 14990,
      instrucciones_pago: { monto: 14990, referencia: 'Pedido 81', datos: [] } } });
    montar('/suscripcion/1', <SuscribirsePlan />, '/suscripcion/:planId');

    const boton = await screen.findByRole('button', { name: /Suscribirme y pagar/ });
    expect(boton).toBeDisabled();
    expect(screen.getByText('Elige qué quieres recibir.')).toBeInTheDocument();
    // Sin stock para una entrega no se puede elegir (RN-03)
    expect(screen.getByRole('radio', { name: /Agotado/ })).toBeDisabled();

    fireEvent.click(screen.getByRole('radio', { name: /Bourbon Rosado/ }));
    expect(screen.getByRole('option', { name: 'Molienda: Molido (sin stock)' })).toBeDisabled();
    fireEvent.change(screen.getByLabelText('Opción'), { target: { value: 'BR-GRANO' } });
    await waitFor(() => expect(screen.getByLabelText('Nombre de quien recibe')).toHaveValue('Ana Pérez'));
    fireEvent.click(screen.getByRole('radio', { name: 'Transferencia bancaria' }));
    expect(boton).toBeDisabled();
    expect(screen.getByRole('link', { name: /Términos y Condiciones/ })).toHaveAttribute('href', '/legal/terminos');

    fireEvent.click(screen.getByRole('checkbox', { name: /Acepto los/ }));
    expect(boton).toBeEnabled();
    expect(boton).toHaveTextContent('Suscribirme y pagar $14.990');
    fireEvent.click(boton);

    await waitFor(() => expect(clienteAxios.post).toHaveBeenCalledWith('ventas/suscripciones/', {
      plan_id: 1, producto_mongo_id: 'p1', variante_sku: 'BR-GRANO', proveedor_logistico: 'RETIRO_LOCAL',
      direccion_envio_snapshot: {}, nombre_destinatario: 'Ana Pérez', telefono_destinatario: '+56912345678',
      metodo_pago: 'TRANSFERENCIA', acepta_terminos: true
    }));
    // Con transferencia se muestran los datos para transferir, como en el checkout
    expect(await screen.findByTestId('destino')).toHaveTextContent('/pedido-recibido?orden=81');
    expect(screen.getByTestId('destino')).toHaveTextContent('Pedido 81');
  });

  it('la entrega coordinada suma su costo y muestra el error del servidor', async () => {
    localStorage.setItem('access_token', 'token');
    respuestas({ ...planYOpciones, 'ventas/suscripciones/planes/': { planes: [{ ...PLAN, envio_gratis: false }], dias_aviso: 3 } });
    clienteAxios.post.mockRejectedValue({ response: { status: 400, data: { detail: 'No hay stock suficiente de esa opción. Elige otra.' } } });
    montar('/suscripcion/1', <SuscribirsePlan />, '/suscripcion/:planId');

    fireEvent.click(await screen.findByRole('radio', { name: /Bourbon Rosado/ }));
    fireEvent.change(screen.getByLabelText('Opción'), { target: { value: 'BR-GRANO' } });
    fireEvent.click(screen.getByRole('radio', { name: 'Entrega coordinada' }));
    await waitFor(() => expect(screen.getByLabelText('Teléfono')).toHaveValue('+56912345678'));
    fireEvent.click(screen.getByRole('checkbox', { name: /Acepto los/ }));

    const boton = screen.getByRole('button', { name: /Suscribirme y pagar/ });
    expect(boton).toHaveTextContent('$17.990');
    fireEvent.click(boton);
    expect(await screen.findByRole('alert')).toHaveTextContent('No hay stock suficiente de esa opción.');
  });
});

describe('Mis suscripciones', () => {
  it('ofrece las acciones que permite el servidor y pagar la entrega pendiente', async () => {
    localStorage.setItem('access_token', 'token');
    respuestas({ 'ventas/suscripciones/mias/': { suscripciones: [suscripcion({
      pedido_pendiente: { orden_id: 82, total: 14990, ciclo_fecha: '2026-11-14', metodo_pago: 'TRANSBANK' } })],
    activas_en_tienda: true } });
    montar('/mis-suscripciones', <MisSuscripciones />, '/mis-suscripciones');

    const tarjeta = (await screen.findByRole('heading', { name: 'Café del mes' })).closest('article');
    expect(within(tarjeta).getByRole('link', { name: 'Pagar esta entrega' })).toHaveAttribute('href', '/mis-suscripciones/pagar/82');
    // Con un pedido por pagar no se ofrece adelantar otro
    expect(within(tarjeta).queryByRole('button', { name: 'Recibirla antes' })).not.toBeInTheDocument();
    for (const nombre of ['Cambiar producto, entrega o pago', 'Saltar la próxima entrega', 'Pausar', 'Cancelar suscripción']) {
      expect(within(tarjeta).getByRole('button', { name: nombre })).toBeInTheDocument();
    }
    expect(within(tarjeta).queryByRole('button', { name: 'Reanudar' })).not.toBeInTheDocument();
  });

  it('pausa tras confirmar y muestra el estado nuevo', async () => {
    localStorage.setItem('access_token', 'token');
    respuestas({ 'ventas/suscripciones/mias/': { suscripciones: [suscripcion()], activas_en_tienda: true } });
    clienteAxios.post.mockResolvedValue({ data: suscripcion({ estado: 'PAUSADA', estado_texto: 'Pausada',
      acciones: ['REANUDAR', 'CANCELAR', 'CAMBIAR'] }) });
    const confirmar = vi.spyOn(window, 'confirm').mockReturnValue(true);
    montar('/mis-suscripciones', <MisSuscripciones />, '/mis-suscripciones');

    fireEvent.click(await screen.findByRole('button', { name: 'Pausar' }));

    expect(await screen.findByText('Pausaste tu suscripción. Puedes reanudarla cuando quieras.')).toBeInTheDocument();
    expect(clienteAxios.post).toHaveBeenCalledWith('ventas/suscripciones/4/pausar/');
    expect(screen.getByText('Pausada')).toBeInTheDocument();
    expect(screen.getByText('En pausa: se fija cuando la reanudes')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Reanudar' })).toBeInTheDocument();
    confirmar.mockRestore();
  });

  it('si no confirma la cancelación no hace nada', async () => {
    localStorage.setItem('access_token', 'token');
    respuestas({ 'ventas/suscripciones/mias/': { suscripciones: [suscripcion()], activas_en_tienda: false } });
    const confirmar = vi.spyOn(window, 'confirm').mockReturnValue(false);
    montar('/mis-suscripciones', <MisSuscripciones />, '/mis-suscripciones');

    expect(await screen.findByText(/La tienda pausó las suscripciones/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Cancelar suscripción' }));
    expect(clienteAxios.post).not.toHaveBeenCalled();
    confirmar.mockRestore();
  });

  it('cambia el medio de pago enviando solo lo que cambió', async () => {
    localStorage.setItem('access_token', 'token');
    respuestas({
      'ventas/suscripciones/mias/': { suscripciones: [suscripcion()], activas_en_tienda: true },
      'ventas/suscripciones/planes/1/opciones/': { productos: PRODUCTOS }
    });
    clienteAxios.patch.mockResolvedValue({ data: suscripcion({ metodo_pago: 'TRANSFERENCIA' }) });
    montar('/mis-suscripciones', <MisSuscripciones />, '/mis-suscripciones');

    fireEvent.click(await screen.findByRole('button', { name: 'Cambiar producto, entrega o pago' }));
    const guardar = screen.getByRole('button', { name: 'Guardar cambios' });
      expect(clienteAxios.get).toHaveBeenCalledWith('ventas/suscripciones/planes/1/opciones/',
        { params: { suscripcion_id: 4 } });
    expect(guardar).toBeDisabled();
    fireEvent.click(screen.getByRole('radio', { name: 'Transferencia bancaria' }));
    fireEvent.click(guardar);

    expect(await screen.findByRole('status')).toHaveTextContent('Guardamos tus cambios');
    expect(clienteAxios.patch).toHaveBeenCalledWith('ventas/suscripciones/4/', { metodo_pago: 'TRANSFERENCIA' });
  });
});

describe('Pagar una entrega (/mis-suscripciones/pagar/:ordenId)', () => {
  it('muestra el pedido pendiente y con transferencia lleva a los datos para transferir', async () => {
    localStorage.setItem('access_token', 'token');
    respuestas({ 'ventas/suscripciones/mias/': { suscripciones: [suscripcion({
      metodo_pago: 'TRANSFERENCIA',
      pedido_pendiente: { orden_id: 82, total: 14990, ciclo_fecha: '2026-11-14', metodo_pago: 'TRANSFERENCIA' } })] } });
    clienteAxios.post.mockResolvedValue({ data: { orden_id: 82, total: 14990, instrucciones_pago: { referencia: 'Pedido 82' } } });
    montar('/mis-suscripciones/pagar/82', <PagarEntrega />, '/mis-suscripciones/pagar/:ordenId');

    expect(await screen.findByText(/Tienes hasta el final del 14 de noviembre de 2026/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Pagar $14.990' }));

    expect(await screen.findByTestId('destino')).toHaveTextContent('/pedido-recibido?orden=82');
    expect(clienteAxios.post).toHaveBeenCalledWith('ventas/mis-pedidos/82/pagar/');
  });

  it('si el pedido ya no está pendiente lo dice', async () => {
    localStorage.setItem('access_token', 'token');
    respuestas({ 'ventas/suscripciones/mias/': { suscripciones: [suscripcion()] } });
    montar('/mis-suscripciones/pagar/82', <PagarEntrega />, '/mis-suscripciones/pagar/:ordenId');

    expect(await screen.findByText(/ya no está esperando su pago/)).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Pagar/ })).not.toBeInTheDocument();
  });
});

describe('Menú de la cuenta', () => {
  it('enlaza a Mis suscripciones solo si la tienda las ofrece', async () => {
    localStorage.setItem('access_token', 'token');
    respuestas({ 'usuarios/me/': { nombre: 'Ana' } });
    const { rerender } = render(<MemoryRouter><MenuUsuario suscripciones={false} /></MemoryRouter>);
    fireEvent.click(await screen.findByRole('button', { name: /Menú de usuario/ }));
    expect(screen.queryByRole('link', { name: 'Mis suscripciones' })).not.toBeInTheDocument();

    rerender(<MemoryRouter><MenuUsuario suscripciones /></MemoryRouter>);
    expect(screen.getByRole('link', { name: 'Mis suscripciones' })).toHaveAttribute('href', '/mis-suscripciones');
  });
});
