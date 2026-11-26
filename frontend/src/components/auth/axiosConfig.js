import axios from 'axios';

// Dirección de la API (termina en /api/). En la tienda publicada es relativa (/api/): el mismo servidor entrega el
// frontend y la API, así que no hay CORS. Se fija al compilar con VITE_API_URL (ver frontend/.env.example).
const BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/';

const clienteAxios = axios.create({
    baseURL: BASE_URL,
    headers: {
        'Content-Type': 'application/json'
    }
});

// Token vencido o inválido (ej. firmado con otra SECRET_KEY): se descarta la sesión local
const cerrarSesionLocal = () => {
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    localStorage.removeItem('rol');
};

// Una sola renovación a la vez, aunque fallen varias peticiones al mismo tiempo
let renovacionEnCurso = null;

const renovarToken = () => {
    if (!renovacionEnCurso) {
        const refresh = localStorage.getItem('refresh_token');
        const peticion = refresh
            // axios directo (no clienteAxios) para no pasar por estos interceptores
            ? axios.post(`${BASE_URL}usuarios/token/refresh/`, { refresh })
            : Promise.reject(new Error('No hay refresh_token'));
        renovacionEnCurso = peticion
            .then(({ data }) => {
                localStorage.setItem('access_token', data.access);
                if (data.refresh) localStorage.setItem('refresh_token', data.refresh);
                return data.access;
            })
            .finally(() => { renovacionEnCurso = null; });
    }
    return renovacionEnCurso;
};

// NUEVO: Interceptor de Peticiones (Inyecta el token)
clienteAxios.interceptors.request.use((config) => {
    const token = localStorage.getItem('access_token');
    if (token) {
        config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
});

// El Interceptor
clienteAxios.interceptors.response.use(
    (response) => {
        // Corregido: usamos 'response.data' en todas las líneas, no 'respuesta'
        if (response.data && response.data.access) {
            localStorage.setItem('access_token', response.data.access);
            localStorage.setItem('refresh_token', response.data.refresh);
            console.log("Token JWT interceptado y guardado con éxito.");
        }
        return response;
    },
    async (error) => {
        const original = error.config;
        // Solo un 401 de una petición que llevaba token, y un único reintento por petición
        if (error.response?.status !== 401 || !original?.headers?.Authorization || original._reintentado) {
            return Promise.reject(error);
        }
        original._reintentado = true;
        try {
            original.headers.Authorization = `Bearer ${await renovarToken()}`;
        } catch {
            // Sin sesión válida: las páginas públicas siguen funcionando y ProtectedRoute lleva al login
            cerrarSesionLocal();
            delete original.headers.Authorization;
        }
        return clienteAxios(original);
    }
);

export default clienteAxios;