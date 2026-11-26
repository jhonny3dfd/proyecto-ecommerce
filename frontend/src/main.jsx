import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.jsx'
import { aplicarPaleta, TEMA_PREDETERMINADO } from './constants/palettes'
import { aplicarTipografia, CLAVE_TIPOGRAFIA, TIPOGRAFIA_PREDETERMINADA } from './constants/tipografias'
import { capturarTokensDeEnlace } from './utils/enlacesConToken'
import { protegerDelTraductor } from './utils/traductorNavegador'

// Los tokens de los enlaces de los correos (nueva contraseña, reseña) salen de la URL antes de que la analítica pueda leerla
capturarTokensDeEnlace()

// Un visitante que traduce la tienda con su navegador no debe dejarla en blanco al comprar
protegerDelTraductor()

// Antes del primer render se pintan la última paleta y la última tipografía conocidas, para que la página no parpadee
aplicarPaleta(localStorage.getItem('ecommerce_palette') || TEMA_PREDETERMINADO)
aplicarTipografia(localStorage.getItem(CLAVE_TIPOGRAFIA) || TIPOGRAFIA_PREDETERMINADA)

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
