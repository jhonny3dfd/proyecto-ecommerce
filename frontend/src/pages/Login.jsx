export default function Login() {
    return (
        <div style={{
            maxWidth: '400px',
            margin: '80px auto',
            padding: '30px',
            border: '1px solid #ccc',
            borderRadius: '8px',
            fontFamily: 'sans-serif'
        }}>
            <h2>Iniciar sesión</h2>

            <p>
                Debes iniciar sesión para acceder a esta página.
            </p>

            <form>
                <div style={{ marginBottom: '15px' }}>
                    <label>Correo:</label>
                    <input
                        type="email"
                        style={{
                            width: '100%',
                            padding: '8px',
                            marginTop: '5px',
                            boxSizing: 'border-box'
                        }}
                    />
                </div>

                <div style={{ marginBottom: '20px' }}>
                    <label>Contraseña:</label>
                    <input
                        type="password"
                        style={{
                            width: '100%',
                            padding: '8px',
                            marginTop: '5px',
                            boxSizing: 'border-box'
                        }}
                    />
                </div>

                <button
                    type="submit"
                    style={{
                        width: '100%',
                        padding: '10px',
                        cursor: 'pointer'
                    }}
                >
                    Iniciar sesión
                </button>
            </form>
        </div>
    );
}