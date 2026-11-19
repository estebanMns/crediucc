import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import Home from "./page";

const approvedApplication = {
  id: 17,
  nombre: "Laura Rojas",
  email: "laura@example.com",
  monto: 1500000,
  decision: "APROBADO",
  motivo: "APROBADO",
  tasa_mensual: 1.2,
  notificado: true,
  creado_en: "2026-01-15T12:00:00Z",
};

const rejectedApplication = {
  ...approvedApplication,
  id: 18,
  decision: "RECHAZADO",
  motivo: "EDAD_FUERA_DE_RANGO",
  tasa_mensual: null,
  creado_en: "fecha-inválida",
};

const CONNECTION_MESSAGE = /No hay conexión con el servicio de créditos/;
const TEST_SECRET = "Clave-Segura-123"; // dato de prueba, no es una credencial real
const loginResponse = {
  token_acceso: "token-ana",
  expira_en: 3600,
  usuario: { id: "u-ana", email: "ana@example.com", nombre_completo: "Ana Pérez", edad: 21, semestre: 5 },
};

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status });
}

const healthNoLogin = () => jsonResponse({ status: "healthy", login: false });
const healthWithLogin = () => jsonResponse({ status: "healthy", login: true });

type Reply = Response | { reject: unknown };
type Routes = Record<string, Reply[]>;

/**
 * Simula la API por ruta ("MÉTODO /ruta"). Cada respuesta se usa una vez;
 * la última de cada ruta se repite para las llamadas siguientes.
 */
function mockApi(routes: Routes) {
  const fetchMock = vi.fn((url: string, init?: RequestInit) => {
    const key = `${init?.method ?? "GET"} ${url}`;
    const queue = routes[key];
    if (!queue?.length) return Promise.reject(new Error(`Ruta no simulada: ${key}`));
    const reply = queue.length > 1 ? queue.shift()! : queue[0];
    return "reject" in reply ? Promise.reject(reply.reject) : Promise.resolve(reply.clone());
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

function callsTo(fetchMock: ReturnType<typeof mockApi>, method: string, url: string) {
  return fetchMock.mock.calls.filter(([calledUrl, init]) => calledUrl === url && (init?.method ?? "GET") === method);
}

/** Navega con el menú lateral, igual que lo haría el usuario. */
async function goTo(label: string) {
  const nav = screen.getByRole("navigation", { name: "Navegación principal" });
  fireEvent.click(within(nav).getByRole("link", { name: label }));
  await waitFor(() => {
    expect(within(nav).getByRole("link", { name: label }).getAttribute("aria-current")).toBe("page");
  });
}

async function openNewRequest() {
  await goTo("Nueva solicitud");
  return screen.findByRole("button", { name: /Evaluar mi solicitud/ });
}

function fillApplicationForm({ monto = "1.500.000" } = {}) {
  fireEvent.change(screen.getByPlaceholderText("Ej. Laura Rojas"), { target: { value: "  Ana Pérez  " } });
  fireEvent.change(screen.getByPlaceholderText("nombre@correo.com"), { target: { value: "ana@example.com" } });
  fireEvent.change(screen.getByPlaceholderText("22"), { target: { value: "22" } });
  fireEvent.change(screen.getByPlaceholderText("720"), { target: { value: "720" } });
  fireEvent.change(screen.getByPlaceholderText("2.500.000"), { target: { value: "3.000.000" } });
  fireEvent.change(screen.getByPlaceholderText("1.500.000"), { target: { value: monto } });
}

function submitForm(buttonName: RegExp) {
  const button = screen.getAllByRole("button", { name: buttonName }).find((element) => element.getAttribute("type") === "submit");
  const form = button?.closest("form");
  if (!form) throw new Error("No se encontró el formulario.");
  fireEvent.submit(form);
}

const submitApplication = () => submitForm(/Evaluar mi solicitud/);

/** Sin login (modo CI): historial vacío y abre la pestaña del formulario. */
async function renderNewRequest(extraRoutes: Routes = {}) {
  const fetchMock = mockApi({ "GET /health": [healthNoLogin()], "GET /api/v1/solicitudes": [jsonResponse([])], ...extraRoutes });
  render(<Home />);
  await screen.findByText("Aún no tienes solicitudes");
  await openNewRequest();
  return fetchMock;
}

/** La cookie HttpOnly no es visible para el frontend: la sesión se conoce preguntando a /auth/yo. */
const currentUser = () => jsonResponse(loginResponse.usuario);

function field(name: string): HTMLInputElement {
  const element = document.querySelector(`form [name="${name}"]`);
  if (!element) throw new Error(`No se encontró el campo ${name}`);
  return element as HTMLInputElement;
}

function type(name: string, value: string) {
  fireEvent.change(field(name), { target: { value } });
}

function fillCredentials() {
  type("email", "ana@example.com");
  type("password", TEST_SECRET);
}

type RegistrationData = { nombre_completo: string; edad: string; semestre: string; email: string; password: string; confirmacion: string };
const validRegistration: RegistrationData = {
  nombre_completo: "  ana   pérez  ", edad: "21", semestre: "5", email: "Ana@Example.com", password: TEST_SECRET, confirmacion: TEST_SECRET,
};

async function openRegistration() {
  await screen.findByRole("heading", { name: "Ingresa a tu cuenta" });
  fireEvent.click(screen.getByRole("button", { name: "Crear cuenta" }));
  await screen.findByRole("heading", { name: "Crea tu cuenta" });
}

function fillRegistration(changes: Partial<RegistrationData> = {}) {
  for (const [name, value] of Object.entries({ ...validRegistration, ...changes })) type(name, value);
}

describe("CrediUCC home", () => {
  beforeEach(() => {
    window.history.replaceState(null, "", "/");
  });

  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
  });

  // ----------------------------------------------------------- pestañas
  it("separa Resumen, Nueva solicitud y Mis solicitudes en pestañas", async () => {
    mockApi({ "GET /health": [healthNoLogin()], "GET /api/v1/solicitudes": [jsonResponse([])] });

    render(<Home />);
    await screen.findByText("Aún no tienes solicitudes");
    expect(screen.getByRole("region", { name: "Resumen de solicitudes" })).toBeTruthy();
    expect(screen.queryByRole("button", { name: /Evaluar mi solicitud/ })).toBeNull();
    expect(screen.queryByRole("table")).toBeNull();

    await openNewRequest();
    expect(screen.queryByRole("region", { name: "Resumen de solicitudes" })).toBeNull();
    expect(within(screen.getByRole("banner")).getByText("Nueva solicitud")).toBeTruthy();

    await goTo("Mis solicitudes");
    expect(await screen.findByRole("table")).toBeTruthy();
    expect(screen.queryByRole("button", { name: /Evaluar mi solicitud/ })).toBeNull();

    await goTo("Resumen");
    expect(screen.getByRole("region", { name: "Resumen de solicitudes" })).toBeTruthy();
  });

  it("muestra métricas en Resumen y el historial completo en Mis solicitudes", async () => {
    mockApi({ "GET /health": [healthNoLogin()], "GET /api/v1/solicitudes": [jsonResponse([approvedApplication, rejectedApplication])] });

    render(<Home />);

    const summary = await screen.findByRole("region", { name: "Resumen de solicitudes" });
    await waitFor(() => expect(within(summary).getByText("2")).toBeTruthy());
    expect(within(summary).getByText("1")).toBeTruthy();
    expect(screen.getByText("Servicio activo")).toBeTruthy();
    expect(within(screen.getByRole("article", { name: "Solicitudes recientes" })).getByText("Solicitud #18")).toBeTruthy();

    await goTo("Mis solicitudes");
    const table = await screen.findByRole("table");
    expect(within(table).getByText("Solicitud #17")).toBeTruthy();
    expect(within(table).getByText("Aprobada")).toBeTruthy();
    expect(within(table).getByText("Rechazada")).toBeTruthy();
    expect(within(table).getAllByText("—")).toHaveLength(2);
  });

  // ------------------------------------------------------- formulario
  it("formatea los montos con puntos de miles mientras se escriben", async () => {
    await renderNewRequest();

    const monto = screen.getByPlaceholderText("1.500.000") as HTMLInputElement;
    fireEvent.change(monto, { target: { value: "1500000" } });
    expect(monto.value).toBe("1.500.000");
    fireEvent.change(monto, { target: { value: "abc" } });
    expect(monto.value).toBe("");
  });

  it("envía la solicitud en pesos, muestra aprobación y la lleva a Mis solicitudes", async () => {
    const fetchMock = await renderNewRequest({
      "POST /api/v1/solicitudes": [jsonResponse(approvedApplication, 201)],
      "GET /api/v1/solicitudes": [jsonResponse([]), jsonResponse([approvedApplication])],
    });

    fillApplicationForm();
    submitApplication();

    expect(await screen.findByText(/Tu solicitud #17 fue aprobada/)).toBeTruthy();
    const [, init] = callsTo(fetchMock, "POST", "/api/v1/solicitudes")[0];
    expect(JSON.parse(String(init?.body))).toEqual({
      nombre: "Ana Pérez", email: "ana@example.com", edad: 22, score: 720, ingresos: 3000000, monto: 1500000, es_estudiante: true,
    });
    expect((screen.getByPlaceholderText("1.500.000") as HTMLInputElement).value).toBe("");

    fireEvent.click(screen.getByRole("link", { name: /Ver mis solicitudes/ }));
    const table = await screen.findByRole("table");
    expect(await within(table).findByText("Solicitud #17")).toBeTruthy();
  });

  it("permite cerrar el resultado para hacer otra solicitud", async () => {
    await renderNewRequest({ "POST /api/v1/solicitudes": [jsonResponse(approvedApplication, 201)] });

    fillApplicationForm();
    submitApplication();
    await screen.findByText(/Tu solicitud #17 fue aprobada/);

    fireEvent.click(screen.getByRole("button", { name: "Hacer otra solicitud" }));
    expect(screen.queryByText(/Tu solicitud #17 fue aprobada/)).toBeNull();
  });

  it("no envía la solicitud si el monto está fuera de rango", async () => {
    const fetchMock = await renderNewRequest();

    fillApplicationForm({ monto: "50.000" });
    submitApplication();

    expect(await screen.findByText(/El monto debe estar entre \$100.000 y \$5.000.000 COP/)).toBeTruthy();
    expect(callsTo(fetchMock, "POST", "/api/v1/solicitudes")).toHaveLength(0);
  });

  it.each([
    ["el motivo de rechazo", jsonResponse(rejectedApplication, 201), /La edad debe estar entre 18 y 65 años/],
    ["errores de validación de la API", jsonResponse({ detail: [{ msg: "El correo no es válido" }] }, 422), /El correo no es válido/],
    ["un mensaje general sin detalle", jsonResponse({}, 400), /No pudimos procesar la solicitud/],
    ["un detalle de formato desconocido", jsonResponse({ detail: { code: "invalid" } }, 400), /Revisa los datos ingresados/],
    ["la API caída detrás del proxy", new Response("<html>Internal Server Error</html>", { status: 500 }), CONNECTION_MESSAGE],
    ["una respuesta que no es JSON", new Response("no es json", { status: 201 }), CONNECTION_MESSAGE],
  ])("explica %s", async (_caso, reply, expected) => {
    await renderNewRequest({ "POST /api/v1/solicitudes": [reply] });

    fillApplicationForm();
    submitApplication();

    expect(await screen.findByText(expected)).toBeTruthy();
  });

  it.each([
    ["la red falla", new TypeError("Failed to fetch"), CONNECTION_MESSAGE],
    ["el error no es estándar", "error", /No pudimos enviar tu solicitud/],
  ])("informa cuando %s", async (_caso, failure, expected) => {
    await renderNewRequest({ "POST /api/v1/solicitudes": [{ reject: failure }] });

    fillApplicationForm();
    submitApplication();

    expect(await screen.findByText(expected)).toBeTruthy();
  });

  it("advierte en el formulario cuando el servicio está sin conexión", async () => {
    mockApi({ "GET /health": [{ reject: new TypeError("Failed to fetch") }], "GET /api/v1/solicitudes": [{ reject: new TypeError("x") }] });

    render(<Home />);
    expect(await screen.findByText("Sin conexión")).toBeTruthy();
    await openNewRequest();

    expect(within(screen.getByRole("alert")).getByText(CONNECTION_MESSAGE)).toBeTruthy();
  });

  // --------------------------------------------------------- historial
  it("permite recuperar el historial después de un error al cargar", async () => {
    mockApi({
      "GET /health": [{ reject: new TypeError("Failed to fetch") }],
      "GET /api/v1/solicitudes": [jsonResponse([{}]), { reject: new Error("Conexión interrumpida") }, jsonResponse([])],
    });

    render(<Home />);
    expect(await screen.findByText(/No pudimos cargar tus solicitudes/)).toBeTruthy();
    expect(screen.getByText("Sin conexión")).toBeTruthy();

    await goTo("Mis solicitudes");
    const refresh = () => screen.getByRole("button", { name: "Actualizar solicitudes" });
    fireEvent.click(refresh());
    await waitFor(() => expect(refresh().hasAttribute("disabled")).toBe(false));
    expect(screen.getByText(/No pudimos cargar tus solicitudes/)).toBeTruthy();

    fireEvent.click(refresh());
    await waitFor(() => expect(screen.queryByText(/No pudimos cargar tus solicitudes/)).toBeNull());
    expect(screen.getByText("Aún no tienes solicitudes")).toBeTruthy();
  });

  it("rechaza respuestas de historial con formato inválido", async () => {
    mockApi({ "GET /health": [healthNoLogin()], "GET /api/v1/solicitudes": [jsonResponse({})] });

    render(<Home />);

    expect(await screen.findByText(/No pudimos cargar tus solicitudes/)).toBeTruthy();
    expect(screen.getByText("Servicio activo")).toBeTruthy();
  });

  // ------------------------------------------------------------- login
  it("sin login configurado no pide credenciales ni muestra cerrar sesión", async () => {
    mockApi({ "GET /health": [healthNoLogin()], "GET /api/v1/solicitudes": [jsonResponse([])] });

    render(<Home />);
    await screen.findByText("Aún no tienes solicitudes");
    expect(screen.queryByRole("button", { name: "Mi perfil" })).toBeNull();
    expect(screen.getByText("estudiante.")).toBeTruthy();
  });

  it("con login activo pide ingresar y luego carga solo las solicitudes del usuario", async () => {
    const fetchMock = mockApi({
      "GET /health": [healthWithLogin()],
      "POST /api/v1/auth/ingreso": [jsonResponse(loginResponse)],
      "GET /api/v1/solicitudes": [jsonResponse([approvedApplication])],
    });

    render(<Home />);
    expect(await screen.findByRole("heading", { name: "Ingresa a tu cuenta" })).toBeTruthy();
    expect(callsTo(fetchMock, "GET", "/api/v1/solicitudes")).toHaveLength(0);

    fillCredentials();
    submitForm(/^Ingresar$/);

    expect(await screen.findByRole("button", { name: "Mi perfil" })).toBeTruthy();
    expect(screen.getByText("Ana.")).toBeTruthy(); // "Hola, Ana."
    const [, loginInit] = callsTo(fetchMock, "POST", "/api/v1/auth/ingreso")[0];
    expect(JSON.parse(String(loginInit?.body))).toEqual({ email: "ana@example.com", password: TEST_SECRET });
    await waitFor(() => expect(callsTo(fetchMock, "GET", "/api/v1/solicitudes")).toHaveLength(1));
    const [, listInit] = callsTo(fetchMock, "GET", "/api/v1/solicitudes")[0];
    expect(listInit?.headers).toBeUndefined(); // el JWT viaja en la cookie HttpOnly, no en JavaScript
    expect(window.localStorage.length).toBe(0);
  });

  it("muestra el error cuando las credenciales son incorrectas", async () => {
    mockApi({
      "GET /health": [healthWithLogin()],
      "POST /api/v1/auth/ingreso": [jsonResponse({ detail: "Correo o contraseña incorrectos." }, 401)],
    });

    render(<Home />);
    await screen.findByRole("heading", { name: "Ingresa a tu cuenta" });
    fillCredentials();
    submitForm(/^Ingresar$/);

    expect(await screen.findByText("Correo o contraseña incorrectos.")).toBeTruthy();
  });

  it("registra una cuenta con su perfil y, si exige confirmar el correo, vuelve a Ingresar", async () => {
    const mensaje = "Te enviamos un correo para confirmar tu cuenta. Confírmala y luego ingresa.";
    const fetchMock = mockApi({
      "GET /health": [healthWithLogin()],
      "POST /api/v1/auth/registro": [jsonResponse({ requiere_confirmacion: true, sesion: null, mensaje }, 201)],
    });

    render(<Home />);
    await openRegistration();
    fillRegistration();
    submitForm(/Crear mi cuenta/);

    expect(await screen.findByText(mensaje)).toBeTruthy();
    const [, init] = callsTo(fetchMock, "POST", "/api/v1/auth/registro")[0];
    expect(JSON.parse(String(init?.body))).toEqual({
      email: "ana@example.com", password: TEST_SECRET, nombre_completo: "ana pérez", edad: 21, semestre: 5,
    });
    expect(screen.getByRole("heading", { name: "Ingresa a tu cuenta" })).toBeTruthy();
  });

  it("registra una cuenta sin confirmación y entra directamente", async () => {
    mockApi({
      "GET /health": [healthWithLogin()],
      "POST /api/v1/auth/registro": [jsonResponse({ requiere_confirmacion: false, sesion: loginResponse, mensaje: "ok" }, 201)],
      "GET /api/v1/solicitudes": [jsonResponse([])],
    });

    render(<Home />);
    await openRegistration();
    fillRegistration();
    submitForm(/Crear mi cuenta/);

    expect(await screen.findByRole("button", { name: "Mi perfil" })).toBeTruthy();
  });

  it.each([
    ["nombre de una sola palabra", { nombre_completo: "Ana" }, /nombre y apellido/],
    ["nombre con una palabra sin letras", { nombre_completo: "Ana --" }, /solo con letras/],
    ["menor de 16 años", { edad: "15" }, /entre 16 y 100 años/],
    ["edad vacía", { edad: "" }, /entre 16 y 100 años/],
    ["sin semestre", { semestre: "" }, /Selecciona tu semestre/],
    ["correo sin dominio", { email: "ana@correo" }, /correo válido/],
    ["contraseña corta", { password: "abc12", confirmacion: "abc12" }, /entre 8 y 72 caracteres/],
    ["contraseña sin números", { password: "SoloLetras", confirmacion: "SoloLetras" }, /con letras y números/],
    ["contraseña sin letras", { password: "12345678", confirmacion: "12345678" }, /con letras y números/],
    ["contraseña de más de 72 caracteres", { password: "a1".repeat(37), confirmacion: "a1".repeat(37) }, /entre 8 y 72 caracteres/],
    ["contraseñas distintas", { confirmacion: "Otra-Clave-999" }, /Las contraseñas no coinciden/],
  ])("no registra con %s y lo explica en el campo", async (_caso, changes, expected) => {
    const fetchMock = mockApi({ "GET /health": [healthWithLogin()] });

    render(<Home />);
    await openRegistration();
    fillRegistration(changes);
    submitForm(/Crear mi cuenta/);

    expect(await screen.findByText(expected, { selector: "small" })).toBeTruthy(); // mensaje bajo el campo
    expect(screen.getByText("Revisa los campos marcados.")).toBeTruthy();
    expect(callsTo(fetchMock, "POST", "/api/v1/auth/registro")).toHaveLength(0);
  });

  it("valida el correo y la contraseña antes de ingresar", async () => {
    const fetchMock = mockApi({ "GET /health": [healthWithLogin()] });

    render(<Home />);
    await screen.findByRole("heading", { name: "Ingresa a tu cuenta" });
    type("email", "no-es-correo");
    submitForm(/^Ingresar$/);

    expect(await screen.findByText(/correo válido/)).toBeTruthy();
    expect(screen.getByText("Escribe tu contraseña.")).toBeTruthy();
    expect(field("password").getAttribute("aria-invalid")).toBe("true");
    expect(callsTo(fetchMock, "POST", "/api/v1/auth/ingreso")).toHaveLength(0);
  });

  it("muestra el error que devuelve la API al registrarse", async () => {
    mockApi({
      "GET /health": [healthWithLogin()],
      "POST /api/v1/auth/registro": [jsonResponse({ detail: "Ya existe una cuenta con ese correo." }, 400)],
    });

    render(<Home />);
    await openRegistration();
    fillRegistration();
    submitForm(/Crear mi cuenta/);

    expect(await screen.findByText("Ya existe una cuenta con ese correo.")).toBeTruthy();
  });

  it("recupera la sesión de la cookie y muestra el perfil con cerrar sesión", async () => {
    const fetchMock = mockApi({
      "GET /health": [healthWithLogin()],
      "GET /api/v1/auth/yo": [currentUser()],
      "GET /api/v1/solicitudes": [jsonResponse([approvedApplication])],
      "POST /api/v1/auth/salida": [new Response(null, { status: 204 })],
    });

    render(<Home />);
    const profile = await screen.findByRole("button", { name: "Mi perfil" });
    expect(screen.getByText("Ana.")).toBeTruthy();
    expect(within(profile).getByText("AP")).toBeTruthy();

    fireEvent.click(profile);
    const panel = screen.getByRole("region", { name: "Perfil del usuario" });
    expect(within(panel).getByText("Ana Pérez")).toBeTruthy();
    expect(within(panel).getByText("ana@example.com")).toBeTruthy();
    expect(within(panel).getByText("21 años")).toBeTruthy();
    expect(within(panel).getByText("5.º")).toBeTruthy();

    fireEvent.keyDown(document, { key: "Escape" });
    expect(screen.queryByRole("region", { name: "Perfil del usuario" })).toBeNull();
    fireEvent.click(profile);
    fireEvent.click(within(screen.getByRole("region", { name: "Perfil del usuario" })).getByRole("button", { name: /Cerrar sesión/ }));

    expect(await screen.findByRole("heading", { name: "Ingresa a tu cuenta" })).toBeTruthy();
    expect(callsTo(fetchMock, "POST", "/api/v1/auth/salida")).toHaveLength(1);
  });

  it("cierra el menú de perfil al hacer clic fuera", async () => {
    mockApi({ "GET /health": [healthWithLogin()], "GET /api/v1/auth/yo": [currentUser()], "GET /api/v1/solicitudes": [jsonResponse([])] });

    render(<Home />);
    fireEvent.click(await screen.findByRole("button", { name: "Mi perfil" }));
    expect(screen.getByRole("region", { name: "Perfil del usuario" })).toBeTruthy();
    fireEvent.mouseDown(document.body);
    expect(screen.queryByRole("region", { name: "Perfil del usuario" })).toBeNull();
  });

  it("muestra el login si la cookie no tiene una sesión válida", async () => {
    mockApi({ "GET /health": [healthWithLogin()], "GET /api/v1/auth/yo": [jsonResponse({ detail: "x" }, 401)] });

    render(<Home />);
    expect(await screen.findByRole("heading", { name: "Ingresa a tu cuenta" })).toBeTruthy();
  });

  it("vuelve al login si la API rechaza la sesión al cargar el historial", async () => {
    mockApi({
      "GET /health": [healthWithLogin()],
      "GET /api/v1/auth/yo": [currentUser()],
      "GET /api/v1/solicitudes": [jsonResponse({ detail: "x" }, 401)],
    });

    render(<Home />);

    expect(await screen.findByText("Tu sesión expiró. Vuelve a iniciar sesión.")).toBeTruthy();
  });

  it("vuelve al login si la sesión expira al enviar una solicitud y precarga el perfil", async () => {
    mockApi({
      "GET /health": [healthWithLogin()],
      "GET /api/v1/auth/yo": [currentUser()],
      "GET /api/v1/solicitudes": [jsonResponse([])],
      "POST /api/v1/solicitudes": [jsonResponse({ detail: "x" }, 401)],
    });

    render(<Home />);
    await screen.findByRole("button", { name: "Mi perfil" });
    await openNewRequest();
    expect((screen.getByPlaceholderText("nombre@correo.com") as HTMLInputElement).value).toBe("ana@example.com");
    expect((screen.getByPlaceholderText("Ej. Laura Rojas") as HTMLInputElement).value).toBe("Ana Pérez");
    expect((screen.getByPlaceholderText("22") as HTMLInputElement).value).toBe("21");
    fillApplicationForm();
    submitApplication();

    expect(await screen.findByText("Tu sesión expiró. Vuelve a iniciar sesión.")).toBeTruthy();
  });

  // ---------------------------------------------------- campos que solo aceptan lo pedido
  it("permite mostrar y ocultar la contraseña", async () => {
    mockApi({ "GET /health": [healthWithLogin()] });

    render(<Home />);
    await openRegistration();
    expect(field("password").type).toBe("password");

    const [showPassword] = screen.getAllByRole("button", { name: "Mostrar contraseña" });
    fireEvent.click(showPassword);
    expect(field("password").type).toBe("text");
    expect(field("confirmacion").type).toBe("password"); // cada campo tiene su propio botón

    fireEvent.click(screen.getByRole("button", { name: "Ocultar contraseña" }));
    expect(field("password").type).toBe("password");
  });

  it("filtra lo que se escribe: nombres solo con letras y sin espacios en correo y contraseña", async () => {
    mockApi({ "GET /health": [healthWithLogin()] });

    render(<Home />);
    await openRegistration();
    type("nombre_completo", "Ana2 María  Pérez9!");
    type("email", " ana @correo.com ");
    type("password", "Clave 123 ");

    expect(field("nombre_completo").value).toBe("Ana María Pérez");
    expect(field("email").value).toBe("ana@correo.com");
    expect(field("password").value).toBe("Clave123");
  });

  it("los campos numéricos no aceptan letras ni signos", async () => {
    mockApi({ "GET /health": [healthWithLogin()] });

    render(<Home />);
    await openRegistration();
    const age = field("edad");

    expect(fireEvent.keyDown(age, { key: "e" })).toBe(false); // tecla bloqueada
    expect(fireEvent.keyDown(age, { key: "-" })).toBe(false);
    expect(fireEvent.keyDown(age, { key: "7" })).toBe(true);
    expect(fireEvent.keyDown(age, { key: "Backspace" })).toBe(true);
    expect(fireEvent.keyDown(age, { key: "v", ctrlKey: true })).toBe(true); // pegar sigue funcionando
  });

  it("el nombre de la solicitud tampoco acepta números", async () => {
    await renderNewRequest();
    fireEvent.change(screen.getByPlaceholderText("Ej. Laura Rojas"), { target: { value: "Laura 3 Rojas" } });
    expect((screen.getByPlaceholderText("Ej. Laura Rojas") as HTMLInputElement).value).toBe("Laura Rojas");
    expect(fireEvent.keyDown(screen.getByPlaceholderText("720"), { key: "e" })).toBe(false);
  });
});
