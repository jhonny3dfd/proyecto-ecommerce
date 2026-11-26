// Lo que se puede escribir en un teléfono: números, +, espacios, guiones y paréntesis. Que sean 9 dígitos
// chilenos lo revisa el servidor (normalizar_telefono_chile en domain/ventas.py)
export const soloCaracteresDeTelefono = (texto) => texto.replace(/[^\d+\s()-]/g, '');
