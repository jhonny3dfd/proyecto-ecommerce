import { describe, it, expect, afterEach, vi } from 'vitest';
import { render, screen, cleanup, waitFor } from '@testing-library/react';
import FormularioProducto from '../components/FormularioProducto';
import userEvent from '@testing-library/user-event';
import clienteAxios from '../components/auth/axiosConfig';

vi.spyOn(clienteAxios, 'get').mockResolvedValue({data: [],});
vi.spyOn(window, 'alert').mockImplementation(() => {});

const productoExistente = {
  id: 1,
  nombre: 'Camiseta deportiva',
  categoria: 'Ropa',
  activo: true,
  publicado: true,
  atributos_globales: { color: 'Negra', material: 'Algodon' },
};

function renderFormulario(alCancelar = () => {}, alGuardar = () => {}, productoAEditar = null) {
  return render(
    <FormularioProducto
        alCancelar={alCancelar}
        alGuardar={alGuardar}
        productoAEditar={productoAEditar}
    />
  );
}

async function completarFormularioValido(user) {
  await user.type(screen.getByLabelText('Nombre del Producto'),'Camiseta deportiva');

  await user.type(screen.getByLabelText('Categoría'),'Ropa');

  await user.type(screen.getByLabelText('SKU'), 'CAMISETA-001');
  await user.type(screen.getByLabelText('Precio'), '15000');
  await user.type(screen.getByLabelText('Stock'), '10');

  const peso = screen.getByLabelText('Peso (Kg)');
  const alto = screen.getByLabelText('Alto (cm)');
  const ancho = screen.getByLabelText('Ancho (cm)');
  const largo = screen.getByLabelText('Largo (cm)');

  await user.clear(peso);
  await user.type(peso, '1');
  await user.clear(alto);
  await user.type(alto, '10');
  await user.clear(ancho);
  await user.type(ancho, '10');
  await user.clear(largo);
  await user.type(largo, '20');
}

// El de publicar: el formulario también tiene el checkbox de colección privada (SCRUM-197). Su nombre es el estado
const checkboxPublicado = () => screen.getByRole('checkbox', { name: /^(OCULTO|PUBLICADO)$/ });

afterEach(() => {
    cleanup();
    vi.clearAllMocks();
});

describe('FormularioProducto', () => {
    it('muestra el formulario para crear un producto', () => {
        renderFormulario();
        expect(screen.getByText('Crear Nuevo Producto')).toBeInTheDocument();
    });

    it('nombre del producto comienza vacio', () => {
        renderFormulario();
        expect(screen.getByLabelText('Nombre del Producto')).toHaveValue('');
    });

    it('el producto no esta publicado', () => {
        renderFormulario();
        expect(screen.getByText('OCULTO')).toBeInTheDocument();
        expect(checkboxPublicado()).not.toBeChecked();
    });

    it('marcar prodcuto como publicado', async () => {
        renderFormulario();
        expect(screen.getByText('OCULTO')).toBeInTheDocument();
        expect(checkboxPublicado()).not.toBeChecked();

        const user = userEvent.setup();
        const checkbox = checkboxPublicado();
        await user.click(checkbox);

        expect(screen.getByText('PUBLICADO')).toBeInTheDocument();
        expect(checkboxPublicado()).toBeChecked();
    });

    it('publicar y ocultar un producto', async () => {
        renderFormulario();
        expect(screen.getByText('OCULTO')).toBeInTheDocument();
        expect(checkboxPublicado()).not.toBeChecked();

        const user = userEvent.setup();
        const checkbox = checkboxPublicado();
        await user.click(checkbox);

        expect(screen.getByText('PUBLICADO')).toBeInTheDocument();
        expect(checkboxPublicado()).toBeChecked();

        await user.click(checkbox);
        expect(screen.getByText('OCULTO')).toBeInTheDocument();
        expect(checkboxPublicado()).not.toBeChecked();
    });

    it('cancelar la creación de un producto', async () => {
        const cancelarMock = vi.fn();
        renderFormulario(cancelarMock);
        const user = userEvent.setup();
        await user.click(screen.getByRole('button', {name: 'Cerrar formulario de producto'}));
        expect(cancelarMock).toHaveBeenCalled();
    });

    it('impide guardar variantes con SKU duplicados', async () => {
        const guardarMock = vi.fn();
        const postMock = vi.spyOn(clienteAxios, 'post');
        const { container } = renderFormulario(undefined,guardarMock);
        const user = userEvent.setup();

        //Completar los datos de la primera variante
        await user.type(screen.getByLabelText('Nombre del Producto'),'Camiseta deportiva');
        await user.type(screen.getByLabelText('Categoría'),'Ropa');
        const skus = screen.getAllByLabelText('SKU');
        await user.type(skus[0], 'CAMISETA-001');

        //Agregar los datos de la segunda variante
        await user.click(screen.getByRole('button', {name: '+ Nueva Variante',}));
        const skusActualizados = screen.getAllByLabelText('SKU');
        await user.type(skusActualizados[1],'CAMISETA-001');

        //Completar los precios obligatorios
        const precios = screen.getAllByLabelText('Precio');
        await user.type(precios[0], '15000');
        await user.type(precios[1], '15000');

        //Completar el stock obligatorio
        const stocks = screen.getAllByLabelText('Stock');
        await user.type(stocks[0], '10');
        await user.type(stocks[1], '10');

        //Comprobar que el formulario puede enviarse
        const formulario = container.querySelector('form');
        expect(formulario.checkValidity()).toBe(true);

        //Intentar crear el producto
        await user.click(screen.getByRole('button', {name: 'Crear Producto',}));

        //Aparece el error de SKU duplicado
        expect(screen.getByRole('alert')).toHaveTextContent('Cada variante debe tener un SKU único');

        expect(guardarMock).not.toHaveBeenCalled();
        expect(postMock).not.toHaveBeenCalled();
    });

    it('carga los datos del producto al editar', () => {
        renderFormulario(undefined, undefined, productoExistente);

        expect(screen.getByText('Editar Producto')).toBeInTheDocument();
        expect(screen.getByLabelText('Nombre del Producto')).toHaveValue('Camiseta deportiva');
        expect(screen.getByLabelText('Categoría')).toHaveValue('Ropa');
        expect(screen.getByLabelText('Nombre del atributo 1')).toHaveValue('color');
        expect(screen.getByLabelText('Valor del atributo 1')).toHaveValue('Negra');
        expect(screen.getByLabelText('Nombre del atributo 2')).toHaveValue('material');
        expect(screen.getByLabelText('Valor del atributo 2')).toHaveValue('Algodon');
    });

    it('agrega un atributo global al formulario', async () => {
        renderFormulario();
        const user = userEvent.setup();

        await user.click(screen.getByRole('button', { name: 'Agregar atributo global' }));
        expect(screen.getByLabelText('Nombre del atributo 1')).toBeInTheDocument();
        expect(screen.getByLabelText('Valor del atributo 1')).toBeInTheDocument();
    });

    it('modifica el nombre y valor de un atributo global', async () => {
        renderFormulario();
        const user = userEvent.setup();

        await user.click(screen.getByRole('button', { name: 'Agregar atributo global' }));
        await user.type(screen.getByLabelText('Nombre del atributo 1'),'Marca');
        await user.type(screen.getByLabelText('Valor del atributo 1'),'Nike');

        expect(screen.getByLabelText('Nombre del atributo 1')).toHaveValue('Marca');
        expect(screen.getByLabelText('Valor del atributo 1')).toHaveValue('Nike');
    });

    it('elimina un atributo global', async () => {
        renderFormulario(undefined, undefined, productoExistente);
        const user = userEvent.setup();

        expect(screen.getByLabelText('Nombre del atributo 1')).toHaveValue('color');

        expect( screen.getByLabelText('Nombre del atributo 2')).toHaveValue('material');

        await user.click(screen.getByRole('button', { name: 'Borrar atributo 1' }));

        //El atributo color fue eliminado y material ahora ocupa la primera posición
        expect(screen.getByLabelText('Nombre del atributo 1')).toHaveValue('material');

        //Ya no existe un segundo atributo
        expect(screen.queryByLabelText('Nombre del atributo 2')).not.toBeInTheDocument();
    });

    it('agrega una nueva variante', async () => {
        renderFormulario();
        const user = userEvent.setup();

        expect(screen.getByText('Variante #1')).toBeInTheDocument();
        expect(screen.queryByText('Variante #2')).not.toBeInTheDocument();

        await user.click(screen.getByRole('button', { name: '+ Nueva Variante' }));

        expect(screen.getByText('Variante #2')).toBeInTheDocument();
        expect(screen.getAllByLabelText('SKU')).toHaveLength(2);
    });

    it('elimina una variante cuando existe más de una', async () => {
        renderFormulario();
        const user = userEvent.setup();

        await user.click(screen.getByRole('button', { name: '+ Nueva Variante' }));

        expect(screen.getByText('Variante #2')).toBeInTheDocument();

        await user.click(screen.getByRole('button', { name: 'Eliminar Variante 2' }));

        expect(screen.getByText('Variante #1')).toBeInTheDocument();
        expect(screen.queryByText('Variante #2')).not.toBeInTheDocument();
        expect(screen.getAllByLabelText('SKU')).toHaveLength(1);
    });

    it('impide eliminar la única variante del producto', async () => {
        renderFormulario();
        const user = userEvent.setup();

        await user.click(screen.getByRole('button', { name: 'Eliminar Variante 1' }));

        expect(window.alert).toHaveBeenCalledWith('El producto debe tener al menos una variante.');

        expect(screen.getByText('Variante #1')).toBeInTheDocument();
        expect(screen.getAllByLabelText('SKU')).toHaveLength(1);
    });

    it('agrega, modifica y elimina un atributo específico de una variante', async () => {
        renderFormulario();
        const user = userEvent.setup();

        await user.click(screen.getByRole('button', { name: '+ Añadir Atributo' }));

        const nombreAtributo = screen.getByLabelText('Variante 1: nombre del atributo 1');
        const valorAtributo = screen.getByLabelText('Variante 1: valor del atributo 1');

        await user.type(nombreAtributo, 'Talla');
        await user.type(valorAtributo, 'M');

        expect(nombreAtributo).toHaveValue('Talla');
        expect(valorAtributo).toHaveValue('M');

        await user.click(screen.getByRole('button', {name: 'Eliminar atributo 1 de la variante 1'}));

        expect(screen.queryByLabelText('Variante 1: nombre del atributo 1')).not.toBeInTheDocument();
    });

    it('crea un producto y envía los datos transformados al backend', async () => {
        const postMock = vi.spyOn(clienteAxios, 'post').mockResolvedValueOnce({data: { id: 25 }});
        renderFormulario();
        const user = userEvent.setup();
        await completarFormularioValido(user);

        await user.click(screen.getByRole('button', { name: 'Agregar atributo global' }));
        await user.type(screen.getByLabelText('Nombre del atributo 1'),'Material');
        await user.type(screen.getByLabelText('Valor del atributo 1'),'Algodón');

        //Añadimos un atributo específico a la variante
        await user.click(screen.getByRole('button', { name: '+ Añadir Atributo' }));
        await user.type(screen.getByLabelText('Variante 1: nombre del atributo 1'),'Talla');
        await user.type(screen.getByLabelText('Variante 1: valor del atributo 1'),'M');
        await user.click(screen.getByRole('button', { name: 'Crear Producto' }));

        await waitFor(() => {expect(postMock).toHaveBeenCalledTimes(1);});

        expect(postMock).toHaveBeenCalledWith(
            'catalogo/productos/',
            expect.objectContaining({
                nombre: 'Camiseta deportiva',
                categoria: 'Ropa',
                activo: true,
                publicado: false,
                atributos_globales: {
                    material: 'Algodón'
                },
                variantes: [
                    expect.objectContaining({
                        sku: 'CAMISETA-001',
                        precio: 15000,
                        precio_oferta: null,
                        stock: 10,
                        peso_kg: 1,
                        alto_cm: 10,
                        ancho_cm: 10,
                        largo_cm: 20,
                        atributos_variables: {
                            talla: 'M'
                        }
                    })
                ]
            })
        );
        
        expect(window.alert).toHaveBeenCalledWith('¡Producto creado! Ahora puedes agregar imágenes.');

        // Después de guardar, el formulario pasa a mostrar las opciones de edición.
        expect(await screen.findByRole('button', {name: 'Guardar cambios del producto'})).toBeInTheDocument();
    });

    it('muestra un error cuando falla la creación del producto', async () => {
        vi.spyOn(clienteAxios, 'post').mockRejectedValueOnce({
            response: {data: {detail: 'No se pudo crear el producto.'}}});
        renderFormulario();
        const user = userEvent.setup();
        await completarFormularioValido(user);

        await user.click(screen.getByRole('button', { name: 'Crear Producto' }));

        expect(await screen.findByRole('alert')).toHaveTextContent('No se pudo crear el producto.');
    });

    it('edita un producto existente y envía una petición PUT', async () => {
        const productoParaEditar = {
            ...productoExistente,
            id: 50,
            variantes: [
                {
                    sku: 'CAMISETA-001',
                    precio: 15000,
                    precio_oferta: null,
                    stock: 10,
                    peso_kg: 1,
                    alto_cm: 10,
                    ancho_cm: 10,
                    largo_cm: 20,
                    atributos_variables: {
                        talla: 'M'
                    }
                }
            ]
        };

        const putMock = vi.spyOn(clienteAxios, 'put').mockResolvedValueOnce({data: { id: 50 }});

        renderFormulario(undefined, undefined, productoParaEditar);
        const user = userEvent.setup();

        await user.click(screen.getByRole('button', {name: 'Guardar cambios del producto'}));

        await waitFor(() => {expect(putMock).toHaveBeenCalledTimes(1);});

        expect(putMock).toHaveBeenCalledWith(
            'catalogo/productos/50/',
            expect.objectContaining({
                nombre: 'Camiseta deportiva',
                categoria: 'Ropa',
                atributos_globales: {
                    color: 'Negra',
                    material: 'Algodon'
                },
                variantes: [
                    expect.objectContaining({
                        sku: 'CAMISETA-001',
                        atributos_variables: {
                            talla: 'M'
                        }
                    })
                ]
            })
        );

        expect(window.alert).toHaveBeenCalledWith('¡Producto actualizado! Ahora puedes agregar imágenes nuevas.');
    });

    it('llama a alGuardar cuando se pulsa Finalizar después de guardar', async () => {
        const guardarMock = vi.fn();
        vi.spyOn(clienteAxios, 'post').mockResolvedValueOnce({data: { id: 25 }});
        renderFormulario(undefined, guardarMock);
        const user = userEvent.setup();
        await completarFormularioValido(user);

        await user.click(screen.getByRole('button', { name: 'Crear Producto' }));

        //Esperamos a que el guardado termine y aparezca el boton Finalizar
        const botonFinalizar = await screen.findByRole('button', {name: '✓ Finalizar'});

        expect(guardarMock).not.toHaveBeenCalled();
        await user.click(botonFinalizar);
        expect(guardarMock).toHaveBeenCalledTimes(1);
    });
});
