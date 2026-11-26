import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';

vi.mock('../components/auth/axiosConfig', () => ({
  default: {
    get: vi.fn(),
    put: vi.fn()
  }
}));

vi.mock('react-quill-new', () => ({
  default: ({ value, onChange }) => (
    <textarea
      aria-label="Contenido"
      value={value}
      onChange={(e) => onChange(e.target.value, null, 'user')}
    />
  )
}));

vi.mock('../components/carga/Esqueleto', () => ({
  Cargando: ({ children, texto }) => (
    <div>
      <span>{texto}</span>
      {children}
    </div>
  )
}));

vi.mock('../components/carga/EsqueletosPanel', () => ({
  EsqueletoFormulario: () => <div>Esqueleto del formulario</div>
}));

vi.mock('../components/carga/Spinner', () => ({
  default: () => <span>Spinner</span>
}));

import clienteAxios from '../components/auth/axiosConfig';
import GestorPoliticas from '../components/GestorPoliticas';

const PAGINAS_PRUEBA = [
  {
    tipo_pagina: 'TERMINOS',
    titulo: 'Términos de prueba',
    contenido: '<p>Contenido de términos</p>',
    publicada: true,
    ultima_actualizacion: '2026-10-01T12:00:00'
  },
  {
    tipo_pagina: 'PRIVACIDAD',
    titulo: 'Privacidad de prueba',
    contenido: '<p>Contenido de privacidad</p>',
    publicada: true,
    ultima_actualizacion: '2026-10-02T12:00:00'
  },
  {
    tipo_pagina: 'REEMBOLSOS',
    titulo: 'Reembolsos de prueba',
    contenido: '<p>Contenido de reembolsos</p>',
    publicada: false,
    ultima_actualizacion: null
  }
];

describe('GestorPoliticas', () => {
  beforeEach(() => {
    vi.clearAllMocks();

    clienteAxios.get.mockResolvedValue({
      data: PAGINAS_PRUEBA
    });

    clienteAxios.put.mockResolvedValue({
      data: {
        titulo: 'Términos de prueba',
        publicada: true
      }
    });

    vi.spyOn(console, 'error').mockImplementation(() => {});
    vi.spyOn(window, 'confirm').mockReturnValue(true);
  });

  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });
  
  it('muestra el indicador de carga mientras obtiene las páginas legales', () => {
    clienteAxios.get.mockReturnValue(new Promise(() => {}));

    render(<GestorPoliticas />);

    expect(screen.getByText('Cargando páginas legales...')).toBeInTheDocument();
    expect(screen.getByText('Esqueleto del formulario')).toBeInTheDocument();
  });

  it('carga las páginas legales y muestra los datos de términos', async () => {
    render(<GestorPoliticas />);

    expect(await screen.findByDisplayValue('Términos de prueba'))
        .toBeInTheDocument();

    expect(screen.getByText('Términos y Condiciones (Publicada)'))
        .toBeInTheDocument();

    expect(screen.getByRole('button', { name: 'Guardar cambios' }))
        .toBeDisabled();
  });

  it('muestra un error cuando falla la carga de páginas', async () => {
    clienteAxios.get.mockRejectedValue(new Error('Error de servidor'));

    render(<GestorPoliticas />);

    expect(await screen.findByRole('alert'))
        .toHaveTextContent('No se pudieron cargar las páginas legales.');

    expect(console.error).toHaveBeenCalledWith(
        'Error al cargar las páginas legales:',
        expect.any(Error)
    );
  });

  it('muestra advertencia cuando faltan políticas obligatorias por publicar', async () => {
    clienteAxios.get.mockResolvedValue({
        data: [
        {
            ...PAGINAS_PRUEBA[0],
            publicada: false
        },
        {
            ...PAGINAS_PRUEBA[1],
            publicada: false
        }
        ]
    });

    render(<GestorPoliticas />);

    expect(await screen.findByText(/Falta publicar:/))
        .toBeInTheDocument();

    expect(screen.getByText(
        'Términos y Condiciones y Política de Privacidad'
    )).toBeInTheDocument();
  });
  
  it('cambia de página cuando no existen modificaciones pendientes', async () => {
    render(<GestorPoliticas />);

    await screen.findByDisplayValue('Términos de prueba');

    fireEvent.change(screen.getByLabelText('Selecciona la página a editar:'), {
        target: { value: 'PRIVACIDAD' }
    });

    expect(screen.getByLabelText('Título visible en la tienda:'))
        .toHaveValue('Privacidad de prueba');

    expect(window.confirm).not.toHaveBeenCalled();
  });

  it('solicita confirmación cuando existen cambios sin guardar', async () => {
    render(<GestorPoliticas />);

    const titulo = await screen.findByLabelText('Título visible en la tienda:');

    fireEvent.change(titulo, {
        target: { value: 'Nuevo título' }
    });

    fireEvent.change(screen.getByLabelText('Selecciona la página a editar:'), {
        target: { value: 'PRIVACIDAD' }
    });

    expect(window.confirm).toHaveBeenCalledWith(
        'Hay cambios sin guardar en esta página. ¿Descartarlos?'
    );

    expect(titulo).toHaveValue('Privacidad de prueba');
  });

  it('no cambia de página cuando el administrador cancela la confirmación', async () => {
    window.confirm.mockReturnValue(false);

    render(<GestorPoliticas />);

    const titulo = await screen.findByLabelText('Título visible en la tienda:');

    fireEvent.change(titulo, {
        target: { value: 'Cambios pendientes' }
    });

    fireEvent.change(screen.getByLabelText('Selecciona la página a editar:'), {
        target: { value: 'PRIVACIDAD' }
    });

    expect(titulo).toHaveValue('Cambios pendientes');
    expect(screen.getByRole('button', { name: 'Guardar cambios' }))
        .toBeEnabled();
  });

  it('carga un formulario vacío cuando la página seleccionada no existe', async () => {
    clienteAxios.get.mockResolvedValue({
        data: [PAGINAS_PRUEBA[0]]
    });

    render(<GestorPoliticas />);

    await screen.findByDisplayValue('Términos de prueba');

    const selector = screen.getByLabelText('Selecciona la página a editar:');

    fireEvent.change(selector, {
        target: { value: 'REEMBOLSOS' }
    });

    expect(screen.getByLabelText('Título visible en la tienda:'))
        .toHaveValue('');

    expect(screen.getByLabelText('Contenido'))
        .toHaveValue('');
  });
  
  it('habilita guardar cuando se modifica el título', async () => {
    render(<GestorPoliticas />);

    const titulo = await screen.findByLabelText('Título visible en la tienda:');

    fireEvent.change(titulo, {
        target: { value: 'Nuevo título legal' }
    });

    expect(screen.getByRole('button', { name: 'Guardar cambios' }))
        .toBeEnabled();
  });

  it('marca el formulario como modificado cuando cambia el contenido', async () => {
    render(<GestorPoliticas />);

    const contenido = await screen.findByLabelText('Contenido');

    fireEvent.change(contenido, {
        target: { value: '<p>Nuevo contenido legal</p>' }
    });

    expect(screen.getByRole('button', { name: 'Guardar cambios' }))
        .toBeEnabled();
  });

  it('marca el formulario como modificado cuando cambia el estado de publicación', async () => {
    render(<GestorPoliticas />);

    await screen.findByDisplayValue('Términos de prueba');

    fireEvent.click(screen.getByRole('checkbox'));

    expect(screen.getByRole('checkbox')).not.toBeChecked();

    expect(screen.getByRole('button', { name: 'Guardar cambios' }))
        .toBeEnabled();
  });

  it('limita el título a 255 caracteres', async () => {
    render(<GestorPoliticas />);

    const titulo = await screen.findByLabelText('Título visible en la tienda:');

    expect(titulo).toHaveAttribute('maxLength', '255');
  });

  
  it('guarda una página publicada correctamente', async () => {
    clienteAxios.put.mockResolvedValue({
        data: {
        titulo: 'Términos actualizados',
        publicada: true
        }
    });

    render(<GestorPoliticas />);

    const titulo = await screen.findByLabelText('Título visible en la tienda:');

    fireEvent.change(titulo, {
        target: { value: 'Términos actualizados' }
    });

    fireEvent.click(screen.getByRole('button', { name: 'Guardar cambios' }));

    await waitFor(() => {
        expect(clienteAxios.put).toHaveBeenCalledWith(
        'ventas/admin/paginas-legales/terminos/',
        expect.objectContaining({
            titulo: 'Términos actualizados',
            publicada: true
        })
        );
    });

    expect(await screen.findByRole('status'))
        .toHaveTextContent('guardada y publicada');
  });

  it('guarda una página como borrador', async () => {
    clienteAxios.put.mockResolvedValue({
        data: {
        titulo: 'Términos actualizados',
        publicada: false
        }
    });

    render(<GestorPoliticas />);

    const titulo = await screen.findByLabelText('Título visible en la tienda:');

    fireEvent.change(titulo, {
        target: { value: 'Términos actualizados' }
    });

    fireEvent.click(screen.getByRole('checkbox'));

    fireEvent.click(screen.getByRole('button', { name: 'Guardar cambios' }));

    expect(await screen.findByRole('status'))
        .toHaveTextContent('guardada como borrador');
  });

  it('muestra el mensaje de error del contenido cuando falla el guardado', async () => {
    clienteAxios.put.mockRejectedValue({
        response: {
        data: {
            contenido: ['El contenido no puede estar vacío.']
        }
        }
    });

    render(<GestorPoliticas />);

    fireEvent.change(
        await screen.findByLabelText('Título visible en la tienda:'),
        { target: { value: 'Título modificado' } }
    );

    fireEvent.click(screen.getByRole('button', { name: 'Guardar cambios' }));

    expect(await screen.findByRole('alert'))
        .toHaveTextContent('El contenido no puede estar vacío.');
  });

  it('muestra el mensaje de error del título cuando falla el guardado', async () => {
    clienteAxios.put.mockRejectedValue({
        response: {
        data: {
            titulo: ['El título es obligatorio.']
        }
        }
    });

    render(<GestorPoliticas />);

    fireEvent.change(
        await screen.findByLabelText('Título visible en la tienda:'),
        { target: { value: 'Título modificado' } }
    );

    fireEvent.click(screen.getByRole('button', { name: 'Guardar cambios' }));

    expect(await screen.findByRole('alert'))
        .toHaveTextContent('El título es obligatorio.');
  });

  it('muestra el mensaje detail cuando el servidor lo devuelve', async () => {
    clienteAxios.put.mockRejectedValue({
        response: {
        data: {
            detail: 'No tienes permisos para modificar esta página.'
        }
        }
    });

    render(<GestorPoliticas />);

    fireEvent.change(
        await screen.findByLabelText('Título visible en la tienda:'),
        { target: { value: 'Título modificado' } }
    );

    fireEvent.click(screen.getByRole('button', { name: 'Guardar cambios' }));

    expect(await screen.findByRole('alert'))
        .toHaveTextContent('No tienes permisos para modificar esta página.');
  });

  it('muestra el mensaje genérico cuando el servidor no devuelve detalles', async () => {
    clienteAxios.put.mockRejectedValue(new Error('Error desconocido'));

    render(<GestorPoliticas />);

    fireEvent.change(
        await screen.findByLabelText('Título visible en la tienda:'),
        { target: { value: 'Título modificado' } }
    );

    fireEvent.click(screen.getByRole('button', { name: 'Guardar cambios' }));

    expect(await screen.findByRole('alert')).toHaveTextContent('No se pudo guardar la página.');
  });
  
  it('muestra el estado de borrador cuando la página tiene última actualización', async () => {
    clienteAxios.get.mockResolvedValue({
        data: [
        PAGINAS_PRUEBA[0],
        {
            ...PAGINAS_PRUEBA[1],
            publicada: false,
            ultima_actualizacion: '2026-10-02T12:00:00'
        }
        ]
    });

    render(<GestorPoliticas />);

    // Esperar a que termine la carga inicial
    const selector = await screen.findByLabelText(/Selecciona la página a editar/i);
    
    // Seleccionar Política de Privacidad
    fireEvent.change(selector, {target: { value: 'PRIVACIDAD' }});

    // Comprobar que se cargó el título correcto
    expect(await screen.findByDisplayValue('Privacidad de prueba')).toBeInTheDocument();

    expect(screen.getByText('Política de Privacidad (Borrador)')).toBeInTheDocument();
  });

  it('muestra sin redactar cuando la página no tiene actualización', async () => {
    clienteAxios.get.mockResolvedValue({
        data: PAGINAS_PRUEBA
    });

    render(<GestorPoliticas />);

    await screen.findByDisplayValue('Términos de prueba');

    fireEvent.change(screen.getByLabelText('Selecciona la página a editar:'), {
        target: { value: 'REEMBOLSOS' }
    });

    expect(screen.getByText('Política de Reembolsos (Sin redactar)'))
        .toBeInTheDocument();
  });

  it('vuelve a cargar las páginas después de guardar', async () => {
    clienteAxios.put.mockResolvedValue({
        data: {
        titulo: 'Términos actualizados',
        publicada: true
        }
    });

    render(<GestorPoliticas />);

    fireEvent.change(
        await screen.findByLabelText('Título visible en la tienda:'),
        { target: { value: 'Términos actualizados' } }
    );

    fireEvent.click(screen.getByRole('button', { name: 'Guardar cambios' }));

    await waitFor(() => {
        expect(clienteAxios.get).toHaveBeenCalledTimes(2);
    });
  });

  it('muestra la última fecha de actualización de la página seleccionada', async () => {
    render(<GestorPoliticas />);

    await screen.findByDisplayValue('Términos de prueba');

    expect(screen.getByText(/Última actualización:/))
        .toBeInTheDocument();
  });

});
