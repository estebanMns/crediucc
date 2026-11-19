"use client";

import {
  useCallback,
  useEffect,
  useRef,
  useState,
  useSyncExternalStore,
  type ChangeEvent,
  type InputHTMLAttributes,
  type KeyboardEvent,
  type ReactNode,
  type SubmitEvent,
} from "react";

type IconName = "grid" | "plus" | "file" | "user" | "mail" | "check" | "money" | "arrow" | "sparkle" | "refresh" | "lock" | "clock" | "eye" | "eyeOff" | "logout";

type Application = {
  id: number;
  nombre: string;
  email: string;
  monto: number;
  decision: "APROBADO" | "RECHAZADO";
  motivo: string;
  tasa_mensual: number | null;
  notificado: boolean;
  creado_en: string;
};

function isApplication(value: unknown): value is Application {
  if (typeof value !== "object" || value === null) return false;
  const record = value as Record<string, unknown>;
  return (
    typeof record.id === "number" &&
    typeof record.nombre === "string" &&
    typeof record.email === "string" &&
    typeof record.monto === "number" &&
    (record.decision === "APROBADO" || record.decision === "RECHAZADO") &&
    typeof record.motivo === "string" &&
    (typeof record.tasa_mensual === "number" || record.tasa_mensual === null) &&
    typeof record.notificado === "boolean" &&
    typeof record.creado_en === "string"
  );
}

const iconContent: Record<IconName, ReactNode> = {
  grid: <><rect x="3.5" y="3.5" width="7" height="7" rx="1.5" /><rect x="13.5" y="3.5" width="7" height="4" rx="1.5" /><rect x="13.5" y="10.5" width="7" height="10" rx="1.5" /><rect x="3.5" y="13.5" width="7" height="7" rx="1.5" /></>,
  plus: <><circle cx="12" cy="12" r="9" /><path d="M12 7v10M7 12h10" /></>,
  file: <><path d="M7 3.8h7l4 4V20a1.2 1.2 0 0 1-1.2 1.2H7A1.2 1.2 0 0 1 5.8 20V5A1.2 1.2 0 0 1 7 3.8Z" /><path d="M14 4v4h4M9 13h6M9 16.5h6" /></>,
  user: <><circle cx="12" cy="8" r="3.4" /><path d="M5.5 20a6.5 6.5 0 0 1 13 0" /></>,
  mail: <><rect x="3.5" y="5.5" width="17" height="13" rx="2" /><path d="m4.5 7 7.5 5.5L19.5 7" /></>,
  check: <path d="m5 12.5 4.2 4.2L19 7" />,
  money: <path d="M12 3.5v17M16.5 7H10a3 3 0 0 0 0 6h4a3 3 0 0 1 0 6H7" />,
  arrow: <path d="M5 12h14M13 6l6 6-6 6" />,
  sparkle: <><path d="m12 3 1.8 6.2L20 11l-6.2 1.8L12 19l-1.8-6.2L4 11l6.2-1.8L12 3Z" /><path d="m19 16 .8 2.2L22 19l-2.2.8L19 22l-.8-2.2L16 19l2.2-.8L19 16Z" /></>,
  refresh: <><path d="M20 7v5h-5M4 17v-5h5" /><path d="M5.6 9A7 7 0 0 1 18 6.5L20 12M4 12l2 5.5A7 7 0 0 0 18.4 15" /></>,
  lock: <><rect x="5" y="10" width="14" height="11" rx="2" /><path d="M8 10V7a4 4 0 0 1 8 0v3" /></>,
  clock: <><circle cx="12" cy="12" r="9" /><path d="M12 7v5l3 2" /></>,
  eye: <><path d="M2.5 12S6 5.5 12 5.5 21.5 12 21.5 12 18 18.5 12 18.5 2.5 12 2.5 12Z" /><circle cx="12" cy="12" r="3" /></>,
  eyeOff: <><path d="M3 3l18 18M10.6 6.1A9.6 9.6 0 0 1 12 6c6 0 9.5 6 9.5 6a17 17 0 0 1-3 3.7M6.6 7.7A17.4 17.4 0 0 0 2.5 12S6 18 12 18a9 9 0 0 0 4.3-1.1" /><path d="M9.9 9.9a3 3 0 0 0 4.2 4.2" /></>,
  logout: <><path d="M15 4h3a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2h-3M10 16l-4-4 4-4M6 12h10" /></>,
};

function Icon({ name, className = "" }: Readonly<{ name: IconName; className?: string }>) {
  return (
    <svg
      aria-hidden="true"
      className={className}
      fill="none"
      stroke="currentColor"
      strokeLinecap="round"
      strokeLinejoin="round"
      strokeWidth="1.7"
      viewBox="0 0 24 24"
    >
      {iconContent[name]}
    </svg>
  );
}

const currency = new Intl.NumberFormat("es-CO", {
  style: "currency",
  currency: "COP",
  maximumFractionDigits: 0,
});

const dateTime = new Intl.DateTimeFormat("es-CO", {
  dateStyle: "medium",
  timeStyle: "short",
});

const rejectionReasons: Record<string, string> = {
  EDAD_FUERA_DE_RANGO: "La edad debe estar entre 18 y 65 años.",
  SCORE_INSUFICIENTE: "El score mínimo requerido es 600.",
  INGRESOS_INSUFICIENTES: "Los ingresos mensuales no alcanzan el mínimo requerido ($2.000.000 COP).",
};

// ------------------------------------------------------------------ navegación por pestañas
type View = "resumen" | "nueva" | "solicitudes";

const VIEWS: ReadonlyArray<{ view: View; hash: string; label: string; icon: IconName }> = [
  { view: "resumen", hash: "#resumen", label: "Resumen", icon: "grid" },
  { view: "nueva", hash: "#nueva-solicitud", label: "Nueva solicitud", icon: "plus" },
  { view: "solicitudes", hash: "#mis-solicitudes", label: "Mis solicitudes", icon: "file" },
];

function viewFromHash(hash: string): View {
  return VIEWS.find((item) => item.hash === hash)?.view ?? "resumen";
}

function subscribeToHash(onChange: () => void) {
  window.addEventListener("hashchange", onChange);
  return () => window.removeEventListener("hashchange", onChange);
}

const readHash = () => window.location.hash;
const readServerHash = () => "";

// ------------------------------------------------------------------ montos en pesos colombianos
const MONTO_MINIMO = 100_000;
const MONTO_MAXIMO = 5_000_000;
const CONNECTION_ERROR = "No hay conexión con el servicio de créditos. Verifica que la API esté encendida.";

function groupThousands(digits: string): string {
  const groups: string[] = [];
  for (let end = digits.length; end > 0; end -= 3) {
    groups.unshift(digits.slice(Math.max(0, end - 3), end));
  }
  return groups.join(".");
}

/** Deja solo dígitos y los agrupa con puntos de miles: "1500000" -> "1.500.000". */
function formatPesosInput(text: string): string {
  const digits = text.replaceAll(/\D/g, "").replace(/^0+(?=\d)/, "");
  return digits ? groupThousands(digits) : "";
}

/** Convierte "1.500.000" (o "1500000") en 1500000; devuelve NaN si no hay dígitos. */
function parsePesos(text: string): number {
  const digits = text.replaceAll(/\D/g, "");
  return digits ? Number(digits) : Number.NaN;
}

function validateAmounts(ingresos: number, monto: number): string | null {
  if (Number.isNaN(ingresos)) return "Escribe tus ingresos mensuales en pesos, por ejemplo 2.500.000.";
  if (Number.isNaN(monto) || monto < MONTO_MINIMO || monto > MONTO_MAXIMO) {
    return "El monto debe estar entre $100.000 y $5.000.000 COP.";
  }
  return null;
}

// ------------------------------------------------------------------ comunicación con la API
async function readJson(response: Response): Promise<unknown> {
  const text = await response.text();
  try {
    return JSON.parse(text) as unknown;
  } catch {
    throw new Error(CONNECTION_ERROR);
  }
}

function errorMessage(body: unknown) {
  if (typeof body !== "object" || body === null || !("detail" in body)) {
    return "No pudimos procesar la solicitud. Inténtalo de nuevo.";
  }

  const detail = body.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail
      .map((item) => (typeof item === "object" && item !== null && "msg" in item ? item.msg : ""))
      .filter((message): message is string => typeof message === "string")
      .join(" ");
  }
  return "Revisa los datos ingresados e inténtalo de nuevo.";
}

function submitErrorMessage(error: unknown): string {
  if (error instanceof TypeError) return CONNECTION_ERROR; // fetch rechazado: la red o el proxy no responden
  if (error instanceof Error) return error.message;
  return "No pudimos enviar tu solicitud. Inténtalo de nuevo.";
}

// ------------------------------------------------------------------ sesión (Supabase Auth a través de la API)
/**
 * Perfil del usuario con sesión. El JWT NO vive en el navegador: la API lo guarda en una cookie
 * HttpOnly + SameSite=Strict que JavaScript no puede leer, y el navegador la envía sola.
 */
type Session = { email: string; nombre: string; edad: number | null; semestre: number | null };

const SESSION_EXPIRED = "Tu sesión expiró. Vuelve a iniciar sesión.";
const HISTORY_ERROR = "No pudimos cargar tus solicitudes. Verifica tu conexión e inténtalo de nuevo.";

class UnauthorizedError extends Error {
  constructor() {
    super(SESSION_EXPIRED);
    this.name = "UnauthorizedError";
  }
}

function asRecord(value: unknown): Record<string, unknown> | null {
  return typeof value === "object" && value !== null ? (value as Record<string, unknown>) : null;
}

function profileFrom(value: unknown): Session | null {
  const user = asRecord(value);
  if (!user || typeof user.email !== "string") return null;
  return {
    email: user.email,
    nombre: typeof user.nombre_completo === "string" ? user.nombre_completo : "",
    edad: typeof user.edad === "number" ? user.edad : null,
    semestre: typeof user.semestre === "number" ? user.semestre : null,
  };
}

/** Perfil a partir de la respuesta de /auth/ingreso (o de la "sesion" de /auth/registro). */
function sessionFromResponse(body: unknown): Session | null {
  return profileFrom(asRecord(body)?.usuario);
}

/** Pregunta a la API quién es el usuario de la cookie de sesión; null si no hay sesión válida. */
async function requestCurrentUser(): Promise<Session | null> {
  try {
    const response = await fetch("/api/v1/auth/yo", { cache: "no-store" });
    return response.ok ? profileFrom(await readJson(response)) : null;
  } catch {
    return null;
  }
}

async function requestLogout() {
  try {
    await fetch("/api/v1/auth/salida", { method: "POST" });
  } catch {
    // Sin red: la pantalla se cierra igual y el JWT expira solo.
  }
}

function firstName(session: Session): string {
  return session.nombre.split(" ")[0] || session.email.split("@")[0];
}

function initialsOf(session: Session): string {
  const words = session.nombre.split(" ").filter(Boolean);
  const initials = words.length >= 2 ? words[0][0] + words[1][0] : (words[0] ?? session.email).slice(0, 2);
  return initials.toUpperCase();
}

// ------------------------------------------------------------------ filtros de escritura
const NAME_EXTRA_CHARS = "'-";
const isLetter = (char: string) => char.toLowerCase() !== char.toUpperCase();
const isDigit = (char: string) => char >= "0" && char <= "9";

/** Nombres: solo letras (con tildes y ñ), espacios, apóstrofo y guion. */
const keepNameChars = (value: string) =>
  [...value].filter((char) => isLetter(char) || char === " " || NAME_EXTRA_CHARS.includes(char)).join("").replaceAll("  ", " ");
const withoutSpaces = (value: string) => [...value].filter((char) => char.trim() !== "").join("");

function sanitizeWith(clean: (value: string) => string) {
  return (event: ChangeEvent<HTMLInputElement>) => {
    const value = clean(event.target.value);
    if (value !== event.target.value) event.target.value = value;
  };
}

const onNameChange = sanitizeWith(keepNameChars);
const onNoSpacesChange = sanitizeWith(withoutSpaces);

/** En campos numéricos bloquea letras, signos y la "e" que los navegadores aceptan en type="number". */
function onlyDigitKeys(event: KeyboardEvent<HTMLInputElement>) {
  if (event.key.length === 1 && !isDigit(event.key) && !event.ctrlKey && !event.metaKey) event.preventDefault();
}

/** Contraseña con botón para mostrarla u ocultarla; no permite espacios. */
function SecretInput(props: Readonly<Omit<InputHTMLAttributes<HTMLInputElement>, "type" | "onChange">>) {
  const [visible, setVisible] = useState(false);
  return (
    <>
      <input {...props} onChange={onNoSpacesChange} type={visible ? "text" : "password"} />
      <button
        aria-label={visible ? "Ocultar contraseña" : "Mostrar contraseña"}
        aria-pressed={visible}
        className="ml-1 grid h-7 w-7 shrink-0 place-items-center rounded-md text-[#7d8a81] transition hover:bg-[#eef3ed] hover:text-[#2c5a40]"
        onClick={() => setVisible((current) => !current)}
        title={visible ? "Ocultar contraseña" : "Mostrar contraseña"}
        type="button"
      >
        <Icon className="h-4 w-4" name={visible ? "eyeOff" : "eye"} />
      </button>
    </>
  );
}

type HealthInfo = { online: boolean; loginRequired: boolean };

async function requestHealth(): Promise<HealthInfo> {
  try {
    const response = await fetch("/health", { cache: "no-store" });
    const body = asRecord(await readJson(response).catch(() => null));
    return { online: response.ok, loginRequired: body?.login === true };
  } catch {
    return { online: false, loginRequired: false };
  }
}

async function requestApplications(): Promise<Application[]> {
  const response = await fetch("/api/v1/solicitudes", { cache: "no-store" });
  if (response.status === 401) throw new UnauthorizedError();
  if (!response.ok) throw new Error("No pudimos cargar tus solicitudes.");
  const data = await readJson(response);
  if (!Array.isArray(data)) throw new Error("La respuesta del servicio no tiene el formato esperado.");
  const records = data.filter(isApplication);
  if (records.length !== data.length) throw new Error("La respuesta del servicio no tiene el formato esperado.");
  return records;
}

type Feedback = { message: string; tone: "success" | "error"; application?: Application };

function formText(formData: FormData, field: string): string {
  const value = formData.get(field);
  return typeof value === "string" ? value.trim() : "";
}

function feedbackFor(result: Application): Feedback {
  if (result.decision === "APROBADO") {
    const rate = result.tasa_mensual == null ? "" : ` Tasa mensual: ${result.tasa_mensual}%.`;
    return { message: `¡Listo, ${result.nombre}! Tu solicitud #${result.id} fue aprobada.${rate}`, tone: "success", application: result };
  }
  const reason = rejectionReasons[result.motivo] ?? "No cumple los criterios de aprobación.";
  return { message: `Solicitud #${result.id}: ${reason}`, tone: "error", application: result };
}

function serviceStatus(serviceOnline: boolean | null): { dot: string; label: string } {
  if (serviceOnline === null) return { dot: "animate-pulse bg-[#d1b76a]", label: "Conectando..." };
  if (serviceOnline) return { dot: "bg-[#71b584]", label: "Servicio activo" };
  return { dot: "bg-[#db796a]", label: "Sin conexión" };
}

// ------------------------------------------------------------------ piezas compartidas
function HistoryStatus({ isLoading, error, isEmpty }: Readonly<{ isLoading: boolean; error: string; isEmpty: boolean }>) {
  if (isLoading) {
    return <p className="py-8 text-center text-[10px] text-[#89948d]">Cargando tus solicitudes...</p>;
  }
  if (error) {
    return <output className="block py-7 text-center text-[10px] text-[#a95948]">{error}</output>;
  }
  if (!isEmpty) return null;
  return (
    <div className="grid justify-items-center px-3 py-7 text-center">
      <span className="mb-2 grid h-10 w-10 place-items-center rounded-xl bg-[#f0f5ef] text-[#7a9a7b]"><Icon className="h-5 w-5" name="file" /></span>
      <strong className="font-display text-[11px] text-[#58675d]">Aún no tienes solicitudes</strong>
      <span className="mt-1 text-[9px] text-[#9ca69e]">Cuando envíes una, podrás consultar aquí su estado.</span>
      <a className="mt-2 inline-flex items-center gap-1 text-[9px] font-bold text-[#477553]" href="#nueva-solicitud">Crear mi primera solicitud <Icon className="h-3 w-3" name="arrow" /></a>
    </div>
  );
}

function StatusBadge({ approved }: Readonly<{ approved: boolean }>) {
  return (
    <span className={`inline-flex items-center gap-1 rounded-full px-2 py-1 text-[8px] font-semibold ${approved ? "bg-[#eaf5ec] text-[#54845c]" : "bg-[#fff0eb] text-[#b56e5b]"}`}>
      <i className="h-[5px] w-[5px] rounded-full bg-current" />{approved ? "Aprobada" : "Rechazada"}
    </span>
  );
}

function formatRate(rate: number | null): string {
  return rate == null ? "—" : `${rate.toLocaleString("es-CO")}%`;
}

function formatDate(value: string): string {
  const createdAt = new Date(value);
  return Number.isNaN(createdAt.getTime()) ? "—" : dateTime.format(createdAt);
}

function ConnectionWarning() {
  return (
    <div className="mb-3 flex items-start gap-2 rounded-lg border border-[#eedbd4] bg-[#fff7f4] px-3 py-2.5 text-[10px] leading-relaxed text-[#a95948]" role="alert">
      <span className="font-extrabold">!</span>
      <span>{CONNECTION_ERROR}</span>
    </div>
  );
}

// ------------------------------------------------------------------ vista: Resumen
type HistoryProps = { applications: Application[]; isLoading: boolean; historyError: string };
type SummaryProps = HistoryProps & { userName: string };

function SummaryView({ applications, isLoading, historyError, userName }: Readonly<SummaryProps>) {
  const approvedCount = applications.filter((application) => application.decision === "APROBADO").length;
  const requestedAmount = applications.reduce((sum, application) => sum + Number(application.monto), 0);
  const recent = applications.slice(-3).reverse();

  return (
    <>
      <section className="mb-5 flex items-end justify-between gap-4">
        <div>
          <p className="mb-2 flex items-center gap-2 text-[9px] font-bold tracking-[1.1px] text-[#758c7e]">
            <span className="h-px w-4 bg-[#8eaf91]" /> FINANCIACIÓN PARA TUS METAS
          </p>
          <h1 className="font-display text-[25px] font-extrabold tracking-[-1px] text-[#1c302c] sm:text-[29px]">
            Hola, <span className="text-[#317452]">{userName || "estudiante"}.</span>
          </h1>
          <p className="mt-1 text-[11px] text-[#818b85] sm:text-xs">Un impulso para eso que quieres lograr. ¿Qué tienes en mente?</p>
        </div>
        <a className="inline-flex shrink-0 items-center gap-2 rounded-lg border border-[#dbe5db] bg-white px-2.5 py-2 text-[10px] font-bold text-[#345b44] transition hover:border-[#9fbea4] sm:px-3.5 sm:text-[11px]" href="#nueva-solicitud">
          <Icon className="h-4 w-4" name="plus" /> <span className="sm:hidden">Solicitar</span><span className="hidden sm:inline">Solicitar crédito</span>
        </a>
      </section>

      <section aria-label="Información de CrediUCC" className="relative isolate flex min-h-[190px] overflow-hidden rounded-2xl bg-[#174b3d] px-5 py-6 text-white sm:px-8">
        <div className="pointer-events-none absolute inset-0 -z-10 bg-[radial-gradient(ellipse_at_68%_115%,#72a27955_0,transparent_34%)]" />
        <div className="relative z-10 max-w-[58%] sm:max-w-[56%]">
          <span className="inline-flex items-center gap-2 text-[8px] font-bold tracking-[1.15px] text-[#bed4bd]">
            <Icon className="h-3.5 w-3.5 text-[#d1dba0]" name="sparkle" /> TU FUTURO, A TU RITMO
          </span>
          <h2 className="mt-2 font-display text-[21px] font-bold leading-tight tracking-[-.7px] sm:text-2xl">
            Las grandes ideas<br />merecen <em className="not-italic text-[#c6d9a8]">un comienzo.</em>
          </h2>
          <p className="mt-2 max-w-[340px] text-[9px] leading-relaxed text-[#c0d3ca] sm:text-[10px]">
            Financiación pensada para acompañar tus proyectos y tu vida universitaria.
          </p>
          <a className="mt-2 inline-flex items-center gap-2 text-[10px] font-bold text-[#e1edcc]" href="#nueva-solicitud">
            Conoce tu opción <Icon className="h-3.5 w-3.5" name="arrow" />
          </a>
          <p className="mt-1 text-[8px] font-semibold text-[#d5e4c2] sm:hidden">Tasas desde 1,2% mensual*</p>
        </div>
        <div aria-hidden="true" className="absolute -right-7 top-0 h-full w-[46%] sm:right-[2%] sm:w-[40%]">
          <div className="absolute right-[15%] top-12 h-24 w-52 rotate-[-25deg] rounded-[50%] border border-[#c5d6a64a]" />
          <div className="absolute right-[15%] top-12 h-24 w-52 rotate-[25deg] rounded-[50%] border border-[#c5d6a64a]" />
          <div className="absolute right-[28%] top-5 grid h-36 w-36 place-items-center rounded-full border border-[#b5c98938] bg-[radial-gradient(circle_at_44%_34%,#408468_0,#276b53_45%,#1b5140_78%)] shadow-[0_0_0_18px_#98b98b0a,0_0_0_38px_#98b98b08]">
            <span className="absolute left-9 top-8 grid h-14 w-14 place-items-center rounded-full border border-[#c6aa67] bg-[linear-gradient(145deg,#d7c27f,#aa8540)] text-xl text-[#876e34]">$</span>
            <span className="absolute left-14 top-14 grid h-[68px] w-[68px] place-items-center rounded-full border border-[#e6d98d] bg-[linear-gradient(145deg,#f8edbd,#c99f4e)] font-display text-3xl text-[#826633] shadow-[inset_0_0_0_4px_#f4e5ac,inset_0_0_0_5px_#c79d4c]">
              $<small className="absolute bottom-3 text-[7px] font-bold tracking-[1.5px]">UCC</small>
            </span>
            <span className="absolute left-5 top-3 text-base text-[#d6dfa9]">✳</span>
            <span className="absolute bottom-5 right-4 text-sm text-[#98c7a8]">✦</span>
          </div>
          <div className="absolute bottom-5 right-[1%] hidden items-center gap-2 rounded-lg border border-[#e3e7d74d] bg-[#285d49] px-3 py-2 shadow-lg sm:flex">
            <span className="grid h-6 w-6 place-items-center rounded-md bg-[#dce8c2] text-sm text-[#376747] sm:h-7 sm:w-7 sm:text-lg">↘</span>
            <span><small className="block text-[7px] font-bold tracking-[1px] text-[#bad0bd]">TASAS DESDE</small><strong className="font-display text-sm">1,2% <i className="text-[8px] font-normal text-[#c4d6c3]">mensual</i></strong></span>
          </div>
        </div>
        <p className="absolute bottom-2 right-3 text-right text-[7px] text-[#b5cdbd]">*La tasa final depende de tu perfil y resultado de evaluación.</p>
      </section>

      <section aria-label="Resumen de solicitudes" className="my-4 grid gap-2.5 sm:grid-cols-3">
        <article className="relative flex min-h-[76px] items-center gap-3 overflow-hidden rounded-xl border border-[#e9ede8] bg-white px-4 py-3">
          <span className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-[#e7f3eb] text-[#477954]"><Icon className="h-5 w-5" name="file" /></span>
          <div className="grid min-w-0 gap-0.5"><span className="text-[9px] text-[#7d8981]">Solicitudes registradas</span><strong className="font-display text-xl font-extrabold text-[#20372d]">{applications.length}</strong><small className="text-[8px] text-[#a1aaa4]">En esta sesión</small></div>
          <span className="absolute -right-4 -top-5 h-16 w-16 rounded-full bg-[#e7f3eb] opacity-50" />
        </article>
        <article className="relative flex min-h-[76px] items-center gap-3 overflow-hidden rounded-xl border border-[#e9ede8] bg-white px-4 py-3">
          <span className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-[#f0edf8] text-[#7866a5]"><Icon className="h-5 w-5" name="check" /></span>
          <div className="grid min-w-0 gap-0.5"><span className="text-[9px] text-[#7d8981]">Aprobadas</span><strong className="font-display text-xl font-extrabold text-[#20372d]">{approvedCount}</strong><small className="text-[8px] text-[#a1aaa4]">¡Un paso más cerca!</small></div>
          <span className="absolute -right-4 -top-5 h-16 w-16 rounded-full bg-[#f0edf8] opacity-50" />
        </article>
        <article className="relative flex min-h-[76px] items-center gap-3 overflow-hidden rounded-xl border border-[#e9ede8] bg-white px-4 py-3">
          <span className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-[#fff0e3] text-[#bd8054]"><Icon className="h-5 w-5" name="money" /></span>
          <div className="grid min-w-0 gap-0.5"><span className="text-[9px] text-[#7d8981]">Valor solicitado</span><strong className="truncate font-display text-lg font-extrabold text-[#20372d]">{currency.format(requestedAmount)}</strong><small className="text-[8px] text-[#a1aaa4]">Total acumulado</small></div>
          <span className="absolute -right-4 -top-5 h-16 w-16 rounded-full bg-[#fff0e3] opacity-50" />
        </article>
      </section>

      <section className="grid items-start gap-3.5 lg:grid-cols-[minmax(0,1.8fr)_minmax(245px,.82fr)]">
        <article aria-label="Solicitudes recientes" className="rounded-xl border border-[#e8ece7] bg-white p-4 sm:p-5">
          <div className="mb-3 flex items-center justify-between gap-3">
            <div><p className="text-[8px] font-bold tracking-[1.1px] text-[#82958a]">TU ACTIVIDAD</p><h2 className="mt-1 font-display text-base font-extrabold text-[#1c302c]">Solicitudes recientes</h2></div>
            <a className="inline-flex items-center gap-1 text-[9px] font-bold text-[#477553]" href="#mis-solicitudes">Ver todas <Icon className="h-3 w-3" name="arrow" /></a>
          </div>
          <ul className="m-0 list-none p-0">
            {recent.map((application) => (
              <li className="flex items-center gap-3 border-t border-[#eff1ee] py-2.5 text-[9px] text-[#6f7d73]" key={application.id}>
                <span className="grid gap-0.5"><strong className="text-[#405649]">Solicitud #{application.id}</strong><small className="text-[8px] text-[#a0aaa2]">{formatDate(application.creado_en)}</small></span>
                <span className="ml-auto">{currency.format(application.monto)}</span>
                <StatusBadge approved={application.decision === "APROBADO"} />
              </li>
            ))}
          </ul>
          <HistoryStatus error={historyError} isEmpty={applications.length === 0} isLoading={isLoading} />
        </article>

        <aside className="grid gap-3.5 sm:grid-cols-2 lg:grid-cols-1">
          <article className="rounded-xl border border-[#e8ece7] bg-white p-4 sm:p-5">
            <div className="flex items-center gap-2.5">
              <span className="grid h-8 w-8 place-items-center rounded-lg bg-[#edf4e9] text-[#6c9666]"><Icon className="h-4 w-4" name="sparkle" /></span>
              <div><p className="text-[7px] font-bold tracking-[1px] text-[#82958a]">ANTES DE EMPEZAR</p><h2 className="mt-0.5 font-display text-sm font-extrabold text-[#1c302c]">¿Cómo funciona?</h2></div>
            </div>
            <p className="mb-2 mt-3 text-[9px] leading-relaxed text-[#89948d]">Revisamos tres criterios para darte una respuesta al instante.</p>
            <ol className="m-0 list-none p-0">
              {[["01", "Edad", "Entre 18 y 65 años"], ["02", "Score crediticio", "600 puntos o más"], ["03", "Ingresos mensuales", "Desde $2.000.000 COP"]].map(([number, title, description]) => (
                <li className="flex min-h-[51px] items-center gap-2.5 border-t border-[#edf0ec]" key={number}>
                  <span className="font-display text-[8px] font-bold text-[#acb7ac]">{number}</span>
                  <span className="grid gap-1"><strong className="text-[9px] text-[#46584c]">{title}</strong><small className="text-[8px] text-[#9aa49d]">{description}</small></span>
                  <span className="ml-auto grid h-[17px] w-[17px] place-items-center rounded-full bg-[#edf5ec] text-[9px] text-[#5c8c62]">✓</span>
                </li>
              ))}
            </ol>
          </article>

          <article className="relative isolate min-h-[170px] overflow-hidden rounded-xl bg-[#e9efe1] p-4 sm:p-5">
            <div aria-hidden="true" className="absolute -right-12 -top-14 -z-10 h-48 w-48 rounded-full border border-[#91a9814d] shadow-[0_0_0_16px_#91a9810b,0_0_0_32px_#91a9810b]" />
            <div className="flex items-center gap-1.5 text-[7px] font-bold tracking-[.9px] text-[#718671]">
              <Icon className="h-3.5 w-3.5 text-[#7c9a63]" name="sparkle" /> UN BENEFICIO PARA TI
            </div>
            <h3 className="mt-3 font-display text-lg font-extrabold leading-tight tracking-[-.5px] text-[#284736]">Tu esfuerzo<br />tiene <em className="not-italic text-[#5c8458]">recompensa.</em></h3>
            <p className="relative mt-1.5 max-w-[190px] text-[8px] leading-relaxed text-[#718273]">Si eres estudiante, podrías acceder a una tasa preferencial.</p>
            <a className="mt-2 inline-flex items-center gap-1 text-[8px] font-bold text-[#3a6e4b]" href="#nueva-solicitud">Descubre tu tasa <Icon className="h-3 w-3" name="arrow" /></a>
            <span aria-hidden="true" className="absolute bottom-5 right-5 grid h-14 w-14 rotate-12 place-items-center rounded-full border border-[#c5bf82] bg-[linear-gradient(145deg,#efe4ad,#c6af65)] font-display text-2xl text-[#8a7540] shadow-[inset_0_0_0_4px_#f1e7be,inset_0_0_0_5px_#bd9f4e]">$</span>
          </article>
        </aside>
      </section>
    </>
  );
}

// ------------------------------------------------------------------ vista: Nueva solicitud
const inputBox = "flex h-[38px] items-center rounded-lg border border-[#e5eae4] bg-[#fdfefd] px-2.5 transition focus-within:border-[#80a78a] focus-within:ring-4 focus-within:ring-[#39775112]";
const inputText = "h-full w-full bg-transparent text-[10px] text-[#354c3e] outline-none placeholder:text-[#b1bbb4]";

function ResultCard({ feedback, onNewRequest }: Readonly<{ feedback: Feedback; onNewRequest: () => void }>) {
  const success = feedback.tone === "success";
  return (
    <output
      aria-live="polite"
      className={`mb-4 grid gap-3 rounded-xl border px-4 py-3.5 text-[11px] leading-relaxed ${success ? "border-[#d9e8dc] bg-[#f2f8f2] text-[#3e6e4b]" : "border-[#eedbd4] bg-[#fff7f4] text-[#a95948]"}`}
    >
      <span className="flex items-start gap-2">
        <span className="font-extrabold">{success ? "✓" : "!"}</span>
        <span>{feedback.message}</span>
      </span>
      {feedback.application && (
        <span className="flex flex-wrap gap-2">
          <a className="inline-flex items-center gap-1.5 rounded-lg bg-[#286649] px-3 py-2 text-[10px] font-bold text-white transition hover:bg-[#1e573c]" href="#mis-solicitudes">
            Ver mis solicitudes <Icon className="h-3.5 w-3.5" name="arrow" />
          </a>
          <button className="rounded-lg border border-[#d3dfd4] bg-white px-3 py-2 text-[10px] font-bold text-[#345b44] transition hover:border-[#9fbea4]" onClick={onNewRequest} type="button">
            Hacer otra solicitud
          </button>
        </span>
      )}
    </output>
  );
}

type NewRequestProps = {
  serviceOnline: boolean | null;
  defaultEmail: string;
  defaultName: string;
  defaultAge: number | null;
  onCreated: () => Promise<void>;
  onUnauthorized: () => void;
};

function NewRequestView({ serviceOnline, defaultEmail, defaultName, defaultAge, onCreated, onUnauthorized }: Readonly<NewRequestProps>) {
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [feedback, setFeedback] = useState<Feedback | null>(null);
  const [ingresos, setIngresos] = useState("");
  const [monto, setMonto] = useState("");

  function handlePesosChange(setter: (value: string) => void) {
    return (event: ChangeEvent<HTMLInputElement>) => setter(formatPesosInput(event.target.value));
  }

  async function handleSubmit(event: SubmitEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    if (!form.reportValidity()) return;

    const formData = new FormData(form);
    const payload = {
      nombre: formText(formData, "nombre"),
      email: formText(formData, "email"),
      edad: Number(formData.get("edad")),
      score: Number(formData.get("score")),
      ingresos: parsePesos(ingresos),
      monto: parsePesos(monto),
      es_estudiante: formData.has("es_estudiante"),
    };

    const amountError = validateAmounts(payload.ingresos, payload.monto);
    if (amountError) {
      setFeedback({ message: amountError, tone: "error" });
      return;
    }

    setIsSubmitting(true);
    setFeedback(null);

    try {
      const response = await fetch("/api/v1/solicitudes", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (response.status === 401) {
        onUnauthorized();
        return;
      }
      if (response.status >= 500) throw new Error(CONNECTION_ERROR);
      const body = await readJson(response);
      if (!response.ok) throw new Error(errorMessage(body));
      if (!isApplication(body)) throw new Error("La respuesta del servicio no tiene el formato esperado.");

      setFeedback(feedbackFor(body));
      form.reset();
      setIngresos("");
      setMonto("");
      await onCreated();
    } catch (error) {
      setFeedback({ message: submitErrorMessage(error), tone: "error" });
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <section aria-label="Nueva solicitud" className="mx-auto max-w-[760px]">
      <article className="rounded-xl border border-[#e8ece7] bg-white p-4 sm:p-6">
        <div className="flex items-start justify-between gap-3">
          <div>
            <p className="text-[8px] font-bold tracking-[1.1px] text-[#82958a]">EMPECEMOS</p>
            <h1 className="mt-1 font-display text-base font-extrabold tracking-[-.4px] text-[#1c302c] sm:text-lg">Cuéntanos sobre ti</h1>
            <p className="mt-1 text-[10px] text-[#8a948e]">Completa tus datos y evaluaremos tu solicitud al instante.</p>
          </div>
        </div>

        <div className="my-4 flex items-center gap-2 rounded-lg border border-[#e8eee6] bg-[#f7faf6] px-3 py-2.5 text-[9px] leading-relaxed text-[#7a887f]" role="note">
          <span className="grid h-[18px] w-[18px] shrink-0 place-items-center rounded-full border border-[#a6bda8] font-display text-[10px] font-bold text-[#63866d]">i</span>
          <span>Requisitos: edad entre 18 y 65 años, score de 600 o más e ingresos desde $2.000.000 COP.</span>
        </div>

        {serviceOnline === false && <ConnectionWarning />}
        {feedback && <ResultCard feedback={feedback} onNewRequest={() => setFeedback(null)} />}

        <form className="grid gap-x-3 gap-y-3.5 sm:grid-cols-2" onSubmit={handleSubmit}>
          <label className="grid gap-1.5 sm:col-span-2">
            <span className="text-[9px] font-bold text-[#4a5e52]">Nombre completo <b className="text-[#c7795f]">*</b></span>
            <span className={inputBox}>
              <Icon className="mr-2 h-4 w-4 shrink-0 text-[#9aa79d]" name="user" />
              <input autoComplete="name" className={inputText} defaultValue={defaultName} maxLength={120} name="nombre" onChange={onNameChange} placeholder="Ej. Laura Rojas" required />
            </span>
          </label>

          <label className="grid gap-1.5 sm:col-span-2">
            <span className="text-[9px] font-bold text-[#4a5e52]">Correo electrónico <b className="text-[#c7795f]">*</b></span>
            <span className={inputBox}>
              <Icon className="mr-2 h-4 w-4 shrink-0 text-[#9aa79d]" name="mail" />
              <input autoComplete="email" className={inputText} defaultValue={defaultEmail} maxLength={254} name="email" placeholder="nombre@correo.com" required type="email" />
            </span>
          </label>

          <label className="grid gap-1.5">
            <span className="text-[9px] font-bold text-[#4a5e52]">Edad <b className="text-[#c7795f]">*</b></span>
            <span className={inputBox}>
              <input className={inputText} defaultValue={defaultAge ?? undefined} inputMode="numeric" max={120} min={0} name="edad" onKeyDown={onlyDigitKeys} placeholder="22" required type="number" />
              <span className="text-[9px] text-[#a1aaa4]">años</span>
            </span>
            <small className="text-[8px] text-[#9aa49c]">Elegibilidad: entre 18 y 65 años</small>
          </label>

          <label className="grid gap-1.5">
            <span className="text-[9px] font-bold text-[#4a5e52]">Score crediticio <b className="text-[#c7795f]">*</b></span>
            <span className={inputBox}>
              <input className={inputText} inputMode="numeric" max={850} min={300} name="score" onKeyDown={onlyDigitKeys} placeholder="720" required type="number" />
              <span className="text-[9px] text-[#a1aaa4]">/ 850</span>
            </span>
            <small className="text-[8px] text-[#9aa49c]">Entre 300 y 850. Mínimo para aprobación: 600</small>
          </label>

          <label className="grid gap-1.5">
            <span className="text-[9px] font-bold text-[#4a5e52]">Ingresos mensuales <b className="text-[#c7795f]">*</b></span>
            <span className={inputBox}>
              <span className="mr-2 text-[10px] font-semibold text-[#718577]">$</span>
              <input className={inputText} inputMode="numeric" maxLength={13} name="ingresos" onChange={handlePesosChange(setIngresos)} placeholder="2.500.000" required type="text" value={ingresos} />
              <span className="text-[9px] text-[#a1aaa4]">COP</span>
            </span>
            <small className="text-[8px] text-[#9aa49c]">Mínimo para aprobación: $2.000.000 COP</small>
          </label>

          <label className="flex min-h-[51px] cursor-pointer items-center rounded-lg border border-[#e5eae4] bg-[#fdfefd] px-2.5 py-2">
            <span className="grid gap-1 text-[9px] font-bold text-[#506356]">Beneficio estudiante<small className="text-[8px] font-normal text-[#99a39b]">Cuéntanos si estudias en la UCC</small></span>
            <input className="peer sr-only" defaultChecked name="es_estudiante" type="checkbox" />
            <span aria-hidden="true" className="relative ml-auto h-[18px] w-8 rounded-full bg-[#d4dcd5] transition peer-checked:bg-[#4f8d63] after:absolute after:left-[3px] after:top-[3px] after:h-3 after:w-3 after:rounded-full after:bg-white after:shadow after:transition peer-checked:after:translate-x-3.5 peer-focus-visible:outline peer-focus-visible:outline-2 peer-focus-visible:outline-[#39775155]" />
          </label>

          <label className="grid gap-1.5 sm:col-span-2">
            <span className="text-[9px] font-bold text-[#4a5e52]">¿Cuánto necesitas? <b className="text-[#c7795f]">*</b></span>
            <span className={inputBox}>
              <span className="mr-2 text-[10px] font-semibold text-[#718577]">$</span>
              <input className={inputText} inputMode="numeric" maxLength={9} name="monto" onChange={handlePesosChange(setMonto)} placeholder="1.500.000" required type="text" value={monto} />
              <span className="text-[9px] text-[#a1aaa4]">COP</span>
            </span>
            <small className="text-[8px] text-[#9aa49c]">Puedes solicitar entre $100.000 y $5.000.000 COP</small>
          </label>

          <div className="mt-1 flex flex-col gap-3 border-t border-[#edf0ec] pt-3 sm:col-span-2 sm:flex-row sm:items-center sm:justify-between">
            <p className="m-0 flex items-center gap-1.5 text-[8px] text-[#97a199]">
              <Icon className="h-3.5 w-3.5 text-[#6a9271]" name="clock" /> Evaluación inmediata <span className="text-[#c5ccc6]">·</span> Sin compromiso
            </p>
            <button className="inline-flex min-h-[39px] items-center justify-center gap-2 rounded-lg bg-[#286649] px-4 text-[10px] font-bold text-white transition hover:bg-[#1e573c] disabled:cursor-wait disabled:opacity-60" disabled={isSubmitting} type="submit">
              {isSubmitting ? "Evaluando..." : "Evaluar mi solicitud"}
              <Icon className="h-4 w-4" name="arrow" />
            </button>
          </div>
        </form>
      </article>
    </section>
  );
}

// ------------------------------------------------------------------ vista: Mis solicitudes
type ApplicationsViewProps = HistoryProps & { isRefreshing: boolean; onRefresh: () => void };

function ApplicationsView({ applications, isLoading, historyError, isRefreshing, onRefresh }: Readonly<ApplicationsViewProps>) {
  return (
    <section aria-label="Mis solicitudes" className="rounded-xl border border-[#e8ece7] bg-white p-4 sm:p-5">
      <div className="mb-3.5 flex items-center justify-between gap-3">
        <div><p className="text-[8px] font-bold tracking-[1.1px] text-[#82958a]">TU ACTIVIDAD</p><h1 className="mt-1 font-display text-base font-extrabold text-[#1c302c]">Mis solicitudes</h1></div>
        <div className="flex items-center gap-2">
          <a className="inline-flex items-center gap-1.5 rounded-md bg-[#286649] px-2.5 py-2 text-[9px] font-bold text-white transition hover:bg-[#1e573c]" href="#nueva-solicitud">
            <Icon className="h-3.5 w-3.5" name="plus" /> <span className="hidden sm:inline">Nueva solicitud</span>
          </a>
          <button aria-label="Actualizar solicitudes" className="inline-flex items-center gap-1.5 rounded-md border border-[#e5eae4] px-2.5 py-2 text-[9px] text-[#64746a] transition hover:border-[#b8cdbb] disabled:opacity-50" disabled={isRefreshing} onClick={onRefresh} type="button">
            <Icon className={`h-3.5 w-3.5 ${isRefreshing ? "animate-spin" : ""}`} name="refresh" /> <span className="hidden sm:inline">Actualizar</span>
          </button>
        </div>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[610px] border-collapse text-left">
          <thead className="bg-[#f7f9f6] text-[8px] text-[#929e95]">
            <tr><th className="px-3 py-2.5 font-semibold">Solicitud</th><th className="px-3 py-2.5 font-semibold">Fecha</th><th className="px-3 py-2.5 font-semibold">Monto</th><th className="px-3 py-2.5 font-semibold">Estado</th><th className="px-3 py-2.5 font-semibold">Tasa mensual</th></tr>
          </thead>
          <tbody>
            {applications.map((application) => (
              <tr className="border-b border-[#eff1ee] text-[9px] text-[#6f7d73] last:border-0" key={application.id}>
                <td className="px-3 py-3"><strong className="block text-[#405649]">Solicitud #{application.id}</strong><small className="mt-1 block text-[8px] text-[#a0aaa2]">{application.nombre} · {application.email}</small></td>
                <td className="px-3 py-3">{formatDate(application.creado_en)}</td>
                <td className="px-3 py-3">{currency.format(application.monto)}</td>
                <td className="px-3 py-3"><StatusBadge approved={application.decision === "APROBADO"} /></td>
                <td className="px-3 py-3 font-bold text-[#4e7656]">{formatRate(application.tasa_mensual)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <HistoryStatus error={historyError} isEmpty={applications.length === 0} isLoading={isLoading} />
      <p className="mt-2 flex items-center gap-2 border-t border-[#eff1ee] pt-3 text-[8px] text-[#a0aaa2]">
        <span className="h-[5px] w-[5px] rounded-full bg-[#71b584]" /> Tus solicitudes se guardan mientras la sesión de la aplicación esté activa.
      </p>
    </section>
  );
}

// ------------------------------------------------------------------ pantalla de acceso
type AuthMode = "ingreso" | "registro";

function Brand() {
  return (
    <span className="flex items-center gap-3">
      <span className="grid h-9 w-9 grid-cols-2 place-content-center gap-[3px] rounded-xl border border-[#6f9e84] p-[7px]">
        <i className="rounded-[2px] border border-[#b1d0b9]" />
        <i className="rounded-[2px] bg-[#acc9ae]" />
        <i className="rounded-[2px] bg-[#5e9d7b]" />
        <i className="rounded-[2px] border border-[#b1d0b9]" />
      </span>
      <span className="font-display text-xl font-extrabold tracking-[-1px]">
        credi<span className="text-[#a8c9a7]">ucc</span>
        <small className="mt-1 block text-[8px] font-semibold tracking-[1.2px] text-[#9db5a8]">FINANCIACIÓN ESTUDIANTIL</small>
      </span>
    </span>
  );
}

function registrationMessage(body: unknown): string {
  const message = asRecord(body)?.mensaje;
  return typeof message === "string" ? message : "Cuenta creada. Ya puedes ingresar.";
}

// Reglas de registro (iguales a las de la API en app/api/esquemas.py).
const REGISTRATION_AGE = { min: 16, max: 100 };
const SEMESTERS = Array.from({ length: 12 }, (_, index) => index + 1);
const SECRET_LENGTH = { min: 8, max: 72 };
type FieldName = "nombre_completo" | "edad" | "semestre" | "email" | "password" | "confirmacion";
type FieldErrors = Partial<Record<FieldName, string>>;

function withoutEmpty(errors: FieldErrors): FieldErrors {
  return Object.fromEntries(Object.entries(errors).filter(([, message]) => message)) as FieldErrors;
}

function validateEmail(value: string): string | undefined {
  const [user, domain, ...rest] = value.split("@");
  const valid = rest.length === 0 && !!user && !!domain && domain.includes(".") && !domain.startsWith(".")
    && !domain.endsWith(".") && !value.includes(" ") && value.length <= 254;
  return valid ? undefined : "Escribe un correo válido, por ejemplo nombre@correo.com.";
}

function validateFullName(value: string): string | undefined {
  const words = value.split(" ").filter(Boolean);
  const onlyLetters = words.every((word) =>
    [...word].some(isLetter) && [...word].every((char) => isLetter(char) || NAME_EXTRA_CHARS.includes(char)));
  return words.length >= 2 && onlyLetters && words.join(" ").length <= 120
    ? undefined
    : "Escribe tu nombre completo (nombre y apellido), solo con letras.";
}

function validateSecret(value: string): string | undefined {
  const chars = [...value];
  const valid = value.length >= SECRET_LENGTH.min && value.length <= SECRET_LENGTH.max
    && !chars.some((char) => char.trim() === "") && chars.some(isLetter) && chars.some(isDigit);
  return valid ? undefined : `Debe tener entre ${SECRET_LENGTH.min} y ${SECRET_LENGTH.max} caracteres, con letras y números, y sin espacios.`;
}

function validateRegistration(data: FormData): FieldErrors {
  const age = Number(formText(data, "edad"));
  const semester = Number(formText(data, "semestre"));
  const secret = String(data.get("password") ?? "");
  const errors: FieldErrors = {
    nombre_completo: validateFullName(formText(data, "nombre_completo")),
    email: validateEmail(formText(data, "email")),
    password: validateSecret(secret),
  };
  if (!formText(data, "edad") || !Number.isInteger(age) || age < REGISTRATION_AGE.min || age > REGISTRATION_AGE.max) {
    errors.edad = `La edad debe estar entre ${REGISTRATION_AGE.min} y ${REGISTRATION_AGE.max} años.`;
  }
  if (!SEMESTERS.includes(semester)) errors.semestre = "Selecciona tu semestre (1 a 12).";
  if (!errors.password && secret !== String(data.get("confirmacion") ?? "")) errors.confirmacion = "Las contraseñas no coinciden.";
  return withoutEmpty(errors);
}

function validateLogin(data: FormData): FieldErrors {
  return withoutEmpty({
    email: validateEmail(formText(data, "email")),
    password: String(data.get("password") ?? "") ? undefined : "Escribe tu contraseña.",
  });
}

function AuthField({ label, error, name, children }: Readonly<{ label: string; error?: string; name: FieldName; children: ReactNode }>) {
  return (
    <label className="grid gap-1.5">
      <span className="text-[9px] font-bold text-[#4a5e52]">{label} <b className="text-[#c7795f]">*</b></span>
      <span className={`${inputBox} ${error ? "border-[#e2a99a] bg-[#fffaf8]" : ""}`}>{children}</span>
      {error && <small className="text-[9px] font-semibold text-[#b4553f]" id={`error-${name}`}>{error}</small>}
    </label>
  );
}

function AuthView({ notice, onAuthenticated }: Readonly<{ notice: string; onAuthenticated: (session: Session) => void }>) {
  const [mode, setMode] = useState<AuthMode>("ingreso");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errors, setErrors] = useState<FieldErrors>({});
  const [message, setMessage] = useState<Feedback | null>(notice ? { message: notice, tone: "error" } : null);
  const isLogin = mode === "ingreso";

  function switchMode(next: AuthMode) {
    setMode(next);
    setErrors({});
    setMessage(null);
  }

  const fieldProps = (name: FieldName) => ({
    "aria-describedby": errors[name] ? `error-${name}` : undefined,
    "aria-invalid": errors[name] ? true : undefined,
    name,
  });

  async function handleSubmit(event: SubmitEvent<HTMLFormElement>) {
    event.preventDefault();
    const formData = new FormData(event.currentTarget);
    const found = isLogin ? validateLogin(formData) : validateRegistration(formData);
    setErrors(found);
    if (Object.keys(found).length > 0) {
      setMessage({ message: "Revisa los campos marcados.", tone: "error" });
      return;
    }

    const credentials = { email: formText(formData, "email").toLowerCase(), password: String(formData.get("password") ?? "") };
    const payload = isLogin ? credentials : {
      ...credentials,
      nombre_completo: formText(formData, "nombre_completo").split(" ").filter(Boolean).join(" "),
      edad: Number(formText(formData, "edad")),
      semestre: Number(formText(formData, "semestre")),
    };

    setIsSubmitting(true);
    setMessage(null);
    try {
      const response = await fetch(isLogin ? "/api/v1/auth/ingreso" : "/api/v1/auth/registro", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const body = await readJson(response);
      if (!response.ok) throw new Error(errorMessage(body));

      const session = sessionFromResponse(isLogin ? body : asRecord(body)?.sesion);
      if (session) {
        onAuthenticated(session);
        return;
      }
      if (isLogin) throw new Error("La respuesta del servicio no tiene el formato esperado.");
      // Registro con confirmación de correo: Supabase envía el enlace y luego se ingresa.
      setMode("ingreso");
      setMessage({ message: registrationMessage(body), tone: "success" });
    } catch (error) {
      setMessage({ message: submitErrorMessage(error), tone: "error" });
    } finally {
      setIsSubmitting(false);
    }
  }

  const tabClass = (active: boolean) =>
    `flex-1 rounded-md px-3 py-2 text-[10px] font-bold transition ${active ? "bg-white text-[#1f4a37] shadow-sm" : "text-[#6f8075] hover:text-[#1f4a37]"}`;
  let submitLabel = isLogin ? "Ingresar" : "Crear mi cuenta";
  if (isSubmitting) submitLabel = "Un momento...";

  return (
    <main className="relative isolate grid min-h-screen place-items-center overflow-hidden bg-[#0f3a2f] px-4 py-10">
      {/* Fondo: degradado verde institucional, cuadrícula sutil y anillos decorativos */}
      <div aria-hidden="true" className="pointer-events-none absolute inset-0 -z-10">
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_15%_10%,#2f7a5c_0,transparent_45%),radial-gradient(ellipse_at_85%_90%,#c6d9a855_0,transparent_40%),linear-gradient(160deg,#123f33_0%,#0c3027_55%,#082219_100%)]" />
        <div className="absolute inset-0 bg-[linear-gradient(#ffffff0a_1px,transparent_1px),linear-gradient(90deg,#ffffff0a_1px,transparent_1px)] bg-[size:44px_44px] [mask-image:radial-gradient(ellipse_at_center,black_35%,transparent_80%)]" />
        <div className="absolute -left-24 -top-24 h-80 w-80 rounded-full border border-[#c5d6a62e] shadow-[0_0_0_28px_#98b98b08,0_0_0_60px_#98b98b06]" />
        <div className="absolute -bottom-32 -right-20 h-96 w-96 rounded-full border border-[#c5d6a62e] shadow-[0_0_0_32px_#98b98b08,0_0_0_70px_#98b98b06]" />
        <span className="absolute right-[12%] top-[14%] text-2xl text-[#d6dfa955]">✦</span>
        <span className="absolute bottom-[18%] left-[10%] text-xl text-[#98c7a855]">✳</span>
      </div>

      <div className="grid w-full max-w-[900px] overflow-hidden rounded-2xl border border-[#ffffff26] bg-white shadow-[0_30px_80px_-20px_#00000080] md:grid-cols-[1fr_1.15fr]">
        <section aria-label="Bienvenida" className="relative isolate hidden flex-col justify-between bg-[#174b3d] p-8 text-white md:flex">
          <div className="pointer-events-none absolute inset-0 -z-10 bg-[radial-gradient(ellipse_at_70%_110%,#72a27955_0,transparent_45%)]" />
          <Brand />
          <div>
            <h2 className="font-display text-2xl font-bold leading-tight tracking-[-.7px]">
              Las grandes ideas<br />merecen <em className="not-italic text-[#c6d9a8]">un comienzo.</em>
            </h2>
            <p className="mt-3 max-w-[300px] text-[11px] leading-relaxed text-[#c0d3ca]">
              Solicita tu microcrédito estudiantil, conoce la respuesta al instante y consulta tus solicitudes cuando quieras.
            </p>
          </div>
          <p className="text-[9px] text-[#a8beb2]">Tasas desde 1,2% mensual · Montos de $100.000 a $5.000.000 COP</p>
        </section>

        <section aria-label="Acceso" className="p-6 sm:p-9">
          <div className="mb-6 md:hidden"><span className="inline-flex rounded-xl bg-[#174b3d] px-3 py-2 text-white"><Brand /></span></div>
          <p className="text-[9px] font-bold tracking-[1.1px] text-[#82958a]">{isLogin ? "BIENVENIDO DE NUEVO" : "EMPIEZA HOY"}</p>
          <h1 className="mt-1 font-display text-xl font-extrabold tracking-[-.5px] text-[#1c302c]">
            {isLogin ? "Ingresa a tu cuenta" : "Crea tu cuenta"}
          </h1>

          <div className="my-5 flex gap-1 rounded-lg bg-[#eef3ed] p-1">
            <button aria-pressed={isLogin} className={tabClass(isLogin)} onClick={() => switchMode("ingreso")} type="button">Ingresar</button>
            <button aria-pressed={!isLogin} className={tabClass(!isLogin)} onClick={() => switchMode("registro")} type="button">Crear cuenta</button>
          </div>

          {message && (
            <output
              aria-live="polite"
              className={`mb-4 flex items-start gap-2 rounded-lg border px-3 py-2.5 text-[10px] leading-relaxed ${message.tone === "success" ? "border-[#d9e8dc] bg-[#f2f8f2] text-[#3e6e4b]" : "border-[#eedbd4] bg-[#fff7f4] text-[#a95948]"}`}
            >
              <span className="font-extrabold">{message.tone === "success" ? "✓" : "!"}</span>
              <span>{message.message}</span>
            </output>
          )}

          <form className="grid gap-3.5 sm:grid-cols-2" key={mode} noValidate onSubmit={handleSubmit}>
            {!isLogin && (
              <>
                <div className="sm:col-span-2">
                  <AuthField error={errors.nombre_completo} label="Nombre completo" name="nombre_completo">
                    <Icon className="mr-2 h-4 w-4 shrink-0 text-[#9aa79d]" name="user" />
                    <input autoComplete="name" className={inputText} maxLength={120} onChange={onNameChange} placeholder="Ej. Laura Rojas Gómez" {...fieldProps("nombre_completo")} />
                  </AuthField>
                </div>
                <AuthField error={errors.edad} label="Edad" name="edad">
                  <input className={inputText} inputMode="numeric" max={REGISTRATION_AGE.max} min={REGISTRATION_AGE.min} onKeyDown={onlyDigitKeys} placeholder="Ej. 20" type="number" {...fieldProps("edad")} />
                  <span className="text-[9px] text-[#a1aaa4]">años</span>
                </AuthField>
                <AuthField error={errors.semestre} label="Semestre" name="semestre">
                  <select className={`${inputText} cursor-pointer`} defaultValue="" {...fieldProps("semestre")}>
                    <option disabled value="">Selecciona</option>
                    {SEMESTERS.map((semester) => <option key={semester} value={semester}>{semester}.º semestre</option>)}
                  </select>
                </AuthField>
              </>
            )}
            <div className="sm:col-span-2">
              <AuthField error={errors.email} label="Correo electrónico" name="email">
                <Icon className="mr-2 h-4 w-4 shrink-0 text-[#9aa79d]" name="mail" />
                <input autoComplete="email" className={inputText} maxLength={254} onChange={onNoSpacesChange} placeholder="nombre@correo.com" type="email" {...fieldProps("email")} />
              </AuthField>
            </div>
            <div className={isLogin ? "sm:col-span-2" : ""}>
              <AuthField error={errors.password} label="Contraseña" name="password">
                <Icon className="mr-2 h-4 w-4 shrink-0 text-[#9aa79d]" name="lock" />
                <SecretInput autoComplete={isLogin ? "current-password" : "new-password"} className={inputText} maxLength={SECRET_LENGTH.max} placeholder={isLogin ? "Tu contraseña" : "Letras y números"} {...fieldProps("password")} />
              </AuthField>
            </div>
            {!isLogin && (
              <AuthField error={errors.confirmacion} label="Confirma la contraseña" name="confirmacion">
                <Icon className="mr-2 h-4 w-4 shrink-0 text-[#9aa79d]" name="lock" />
                <SecretInput autoComplete="new-password" className={inputText} maxLength={SECRET_LENGTH.max} placeholder="Repite la contraseña" {...fieldProps("confirmacion")} />
              </AuthField>
            )}
            {!isLogin && (
              <p className="text-[9px] leading-relaxed text-[#8f9a93] sm:col-span-2">
                La contraseña debe tener mínimo {SECRET_LENGTH.min} caracteres, con letras y números, y sin espacios.
              </p>
            )}
            <button className="mt-1 inline-flex min-h-[40px] items-center justify-center gap-2 rounded-lg bg-[#286649] px-4 text-[11px] font-bold text-white transition hover:bg-[#1e573c] disabled:cursor-wait disabled:opacity-60 sm:col-span-2" disabled={isSubmitting} type="submit">
              {submitLabel}
              <Icon className="h-4 w-4" name="arrow" />
            </button>
          </form>
          <p className="mt-5 text-center text-[9px] text-[#8f9a93]">
            Tus datos de acceso los protege Supabase Auth; CrediUCC nunca guarda tu contraseña.
          </p>
        </section>
      </div>
    </main>
  );
}

function ProfileMenu({ session, onLogout }: Readonly<{ session: Session; onLogout: () => void }>) {
  const [open, setOpen] = useState(false);
  const container = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const closeOutside = (event: MouseEvent) => {
      if (!container.current?.contains(event.target as Node)) setOpen(false);
    };
    const closeOnEscape = (event: globalThis.KeyboardEvent) => {
      if (event.key === "Escape") setOpen(false);
    };
    document.addEventListener("mousedown", closeOutside);
    document.addEventListener("keydown", closeOnEscape);
    return () => {
      document.removeEventListener("mousedown", closeOutside);
      document.removeEventListener("keydown", closeOnEscape);
    };
  }, [open]);

  return (
    <div className="relative" ref={container}>
      <button
        aria-expanded={open}
        aria-label="Mi perfil"
        className="flex items-center gap-2 rounded-full py-0.5 pl-0.5 pr-2 transition hover:bg-[#eef3ed]"
        onClick={() => setOpen((current) => !current)}
        type="button"
      >
        <span aria-hidden="true" className="grid h-8 w-8 place-items-center rounded-full border border-[#cfe0d1] bg-[#286649] text-[10px] font-bold text-white">{initialsOf(session)}</span>
        <span className="hidden max-w-[160px] truncate text-[10px] font-semibold text-[#43544b] md:inline">{firstName(session)}</span>
      </button>
      {open && (
        <section aria-label="Perfil del usuario" className="absolute right-0 top-11 z-40 w-[260px] rounded-xl border border-[#e3e9e2] bg-white p-4 shadow-[0_18px_40px_-12px_#0f2a2133]">
          <div className="flex items-center gap-3">
            <span aria-hidden="true" className="grid h-11 w-11 shrink-0 place-items-center rounded-full bg-[#286649] text-sm font-bold text-white">{initialsOf(session)}</span>
            <div className="min-w-0">
              <strong className="block truncate font-display text-[13px] text-[#1c302c]">{session.nombre || "Estudiante UCC"}</strong>
              <span className="block truncate text-[10px] text-[#7d8981]">{session.email}</span>
            </div>
          </div>
          <dl className="my-3 grid grid-cols-2 gap-2 border-y border-[#eef1ed] py-3 text-[10px]">
            <div><dt className="text-[#9aa39d]">Edad</dt><dd className="font-semibold text-[#43544b]">{session.edad == null ? "—" : `${session.edad} años`}</dd></div>
            <div><dt className="text-[#9aa39d]">Semestre</dt><dd className="font-semibold text-[#43544b]">{session.semestre == null ? "—" : `${session.semestre}.º`}</dd></div>
          </dl>
          <button
            className="flex w-full items-center justify-center gap-2 rounded-lg border border-[#eedbd4] bg-[#fff7f4] px-3 py-2 text-[10px] font-bold text-[#a95948] transition hover:bg-[#fdeee8]"
            onClick={onLogout}
            type="button"
          >
            <Icon className="h-4 w-4" name="logout" /> Cerrar sesión
          </button>
        </section>
      )}
    </div>
  );
}

function LoadingScreen() {
  return (
    <main className="grid min-h-screen place-items-center bg-[#f3f6f2]">
      <p className="flex items-center gap-2 text-[11px] text-[#738078]"><span className="h-2 w-2 animate-pulse rounded-full bg-[#d1b76a]" /> Conectando con CrediUCC...</p>
    </main>
  );
}

// ------------------------------------------------------------------ página
export default function Home() {
  const hash = useSyncExternalStore(subscribeToHash, readHash, readServerHash);
  const view = viewFromHash(hash);
  const current = VIEWS.find((item) => item.view === view) ?? VIEWS[0];

  const [applications, setApplications] = useState<Application[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [serviceOnline, setServiceOnline] = useState<boolean | null>(null);
  const [historyError, setHistoryError] = useState("");
  const [loginRequired, setLoginRequired] = useState<boolean | null>(null);
  const [session, setSession] = useState<Session | null>(null);
  const [authNotice, setAuthNotice] = useState("");

  const endSession = useCallback((notice: string) => {
    setSession(null);
    setApplications([]);
    setHistoryError("");
    setAuthNotice(notice);
  }, []);

  const handleUnauthorized = useCallback(() => endSession(SESSION_EXPIRED), [endSession]);

  const loadApplications = useCallback(async () => {
    try {
      setApplications(await requestApplications());
      setHistoryError("");
    } catch (error) {
      if (error instanceof UnauthorizedError) handleUnauthorized();
      else setHistoryError(HISTORY_ERROR);
    }
  }, [handleUnauthorized]);

  useEffect(() => {
    let active = true;

    async function initialize() {
      const health = await requestHealth();
      if (!active) return;
      setServiceOnline(health.online);
      // Con login, la sesión vive en la cookie HttpOnly: se pregunta a la API quién es el usuario.
      const current = health.loginRequired ? await requestCurrentUser() : null;
      if (!active) return;
      setSession(current);
      setLoginRequired(health.loginRequired);
      if (!health.loginRequired || current) await loadApplications();
      if (active) setIsLoading(false);
    }

    void initialize();
    return () => {
      active = false;
    };
  }, [loadApplications]);

  async function handleAuthenticated(next: Session) {
    setSession(next);
    setAuthNotice("");
    setIsLoading(true);
    await loadApplications();
    setIsLoading(false);
  }

  async function handleLogout() {
    await requestLogout();
    endSession("");
  }

  const handleCreated = useCallback(async () => {
    setServiceOnline(true);
    await loadApplications();
  }, [loadApplications]);

  async function handleRefresh() {
    setIsRefreshing(true);
    await loadApplications();
    setIsRefreshing(false);
  }

  const status = serviceStatus(serviceOnline);

  if (loginRequired === null) return <LoadingScreen />;
  if (loginRequired && !session) return <AuthView notice={authNotice} onAuthenticated={(next) => void handleAuthenticated(next)} />;

  return (
    <div className="min-h-screen md:flex">
      <aside className="z-30 flex h-[68px] items-center justify-between bg-[#193b32] px-4 text-white md:fixed md:inset-y-0 md:left-0 md:h-screen md:w-64 md:flex-col md:items-stretch md:px-[18px] md:py-7">
        <a aria-label="CrediUCC, inicio" className="flex items-center gap-3 md:px-2" href="#resumen">
          <span className="grid h-9 w-9 grid-cols-2 place-content-center gap-[3px] rounded-xl border border-[#6f9e84] p-[7px]">
            <i className="rounded-[2px] border border-[#b1d0b9]" />
            <i className="rounded-[2px] bg-[#acc9ae]" />
            <i className="rounded-[2px] bg-[#5e9d7b]" />
            <i className="rounded-[2px] border border-[#b1d0b9]" />
          </span>
          <span className="font-display text-xl font-extrabold tracking-[-1px]">
            credi<span className="text-[#a8c9a7]">ucc</span>
            <small className="mt-1 block text-[8px] font-semibold tracking-[1.2px] text-[#9db5a8]">FINANCIACIÓN ESTUDIANTIL</small>
          </span>
        </a>

        <nav aria-label="Navegación principal" className="flex items-center gap-1 md:mt-14 md:flex-col md:items-stretch">
          {VIEWS.map((item) => {
            const active = item.view === view;
            return (
              <a
                aria-current={active ? "page" : undefined}
                className={`flex h-10 items-center justify-center gap-3 rounded-lg px-3 transition md:justify-start ${active ? "bg-[#2b5145] text-white" : "text-[#bbcbc2] hover:bg-[#2b5145] hover:text-white"}`}
                href={item.hash}
                key={item.view}
                title={item.label}
              >
                <Icon className="h-[18px] w-[18px]" name={item.icon} />
                <span className="hidden text-xs font-medium sm:inline">{item.label}</span>
              </a>
            );
          })}
        </nav>

        <div className="hidden md:mt-auto md:block">
          <div className="grid gap-2 rounded-xl border border-[#436456] bg-[#21463a] p-4">
            <span className="grid h-8 w-8 place-items-center rounded-lg border border-[#62836f] text-[#c8dbb8]">
              <span className="text-base">?</span>
            </span>
            <strong className="text-xs">¿Necesitas ayuda?</strong>
            <span className="text-[10px] text-[#b0c5ba]">Acércate a tu campus UCC para recibir orientación.</span>
          </div>
          <div className="mt-5 flex items-center gap-2 px-1 text-[10px] text-[#a8beb2]">
            <span className="h-2 w-2 rounded-full bg-[#71b584]" />
            <span>Portal CrediUCC</span>
            <span className="ml-auto text-[#819e90]">v1.0</span>
          </div>
        </div>
      </aside>

      <main className="min-w-0 flex-1 md:ml-64">
        <header className="flex h-14 items-center justify-between border-b border-[#e8ece6] bg-[#fbfcfa] px-4 sm:px-7 lg:px-11">
          <div className="flex items-center gap-2 text-[11px] text-[#9aa39d]">
            Portal <span className="text-[#c4cbc6]">/</span> <strong className="font-semibold text-[#43544b]">{current.label}</strong>
          </div>
          <div className="flex items-center gap-3 sm:gap-4">
            <div className="flex items-center gap-2 text-[10px] text-[#738078]" aria-live="polite">
              <span className={`h-2 w-2 rounded-full ${status.dot}`} />
              <span className="hidden sm:inline">{status.label}</span>
            </div>
            <span className="h-6 w-px bg-[#e9ede8]" />
            {session ? (
              <ProfileMenu onLogout={() => void handleLogout()} session={session} />
            ) : (
              <span className="grid h-8 w-8 place-items-center rounded-full border border-[#dfe9df] bg-[#edf4ed] text-[10px] font-bold text-[#426c52]" aria-label="Comunidad UCC">UC</span>
            )}
          </div>
        </header>

        <div className="mx-auto max-w-[1480px] px-4 py-6 sm:px-7 sm:py-8 lg:px-11">
          {view === "resumen" && (
            <SummaryView applications={applications} historyError={historyError} isLoading={isLoading} userName={session ? firstName(session) : ""} />
          )}
          {view === "nueva" && (
            <NewRequestView
              defaultAge={session?.edad ?? null}
              defaultEmail={session?.email ?? ""}
              defaultName={session?.nombre ?? ""}
              onCreated={handleCreated}
              onUnauthorized={handleUnauthorized}
              serviceOnline={serviceOnline}
            />
          )}
          {view === "solicitudes" && (
            <ApplicationsView
              applications={applications}
              historyError={historyError}
              isLoading={isLoading}
              isRefreshing={isRefreshing}
              onRefresh={handleRefresh}
            />
          )}

          <footer className="mt-4 flex items-center gap-1 text-[8px] text-[#a3aca5]">
            <strong className="text-[#65796c]">CrediUCC</strong>
            <span>· Una iniciativa para impulsar tus metas</span>
            <span className="ml-auto">2026</span>
          </footer>
        </div>
      </main>
    </div>
  );
}
