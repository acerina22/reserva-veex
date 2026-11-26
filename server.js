// Reserva VeEX: servidor HTTP + API. Sin framework; solo `pg`.
const http = require("http");
const fs = require("fs");
const path = require("path");
const { Pool } = require("pg");

const pool = new Pool({ connectionString: process.env.DATABASE_URL, max: 5 });
const EQUIPOS = ["VeEX 10G", "VeEX 1G"];
const SALIDA = { retirado: "retirado", devuelto: "devuelto", cancelado: "cancelado" };

function json(res, code, obj) {
  res.writeHead(code, { "Content-Type": "application/json; charset=utf-8", "Cache-Control": "no-store" });
  res.end(JSON.stringify(obj));
}

function leerBody(req) {
  return new Promise((ok, fail) => {
    let s = "";
    req.on("data", (c) => {
      s += c;
      if (s.length > 20000) { req.destroy(); fail(new Error("body grande")); }
    });
    req.on("end", () => { try { ok(s ? JSON.parse(s) : {}); } catch (e) { fail(e); } });
  });
}

const txt = (v, max = 300) => String(v ?? "").trim().slice(0, max);
const fecha = (v) => { const d = new Date(v); return isNaN(d) ? null : d; };

const TZ = "America/Argentina/Buenos_Aires";

async function estadisticas(res, url) {
  const dias = Math.min(90, Math.max(7, Number(url.searchParams.get("dias")) || 14));
  const porDia = await pool.query(
    `WITH dias AS (
       SELECT generate_series((now() AT TIME ZONE $1)::date - ($2::int - 1), (now() AT TIME ZONE $1)::date + 7, interval '1 day')::date AS d)
     SELECT to_char(d,'YYYY-MM-DD') AS dia, r.equipo,
       SUM(EXTRACT(EPOCH FROM (LEAST(r.hasta, ((d+1)::timestamp AT TIME ZONE $1)) - GREATEST(r.desde, (d::timestamp AT TIME ZONE $1))))/3600.0) AS horas
     FROM dias JOIN reservas r ON r.estado <> 'cancelado'
       AND r.desde < ((d+1)::timestamp AT TIME ZONE $1) AND r.hasta > (d::timestamp AT TIME ZONE $1)
     GROUP BY d, r.equipo ORDER BY d`, [TZ, dias]);
  const porSector = await pool.query(
    `SELECT COALESCE(NULLIF(sector,''),'Sin sector') AS sector, count(*)::int AS reservas,
            ROUND(SUM(EXTRACT(EPOCH FROM (hasta - desde))/3600.0)::numeric,1)::float AS horas
     FROM reservas WHERE estado <> 'cancelado' AND desde >= now() - ($1::int * interval '1 day')
     GROUP BY 1 ORDER BY 2 DESC`, [dias]);
  const resumen = await pool.query(
    `SELECT count(*)::int AS reservas,
            COALESCE(ROUND(SUM(EXTRACT(EPOCH FROM (LEAST(hasta, now()) - GREATEST(desde, now() - ($1::int * interval '1 day'))))/3600.0)::numeric,1),0)::float AS horas_usadas,
            count(*) FILTER (WHERE estado='retirado' AND hasta < now())::int AS vencidas
     FROM reservas WHERE estado <> 'cancelado' AND hasta > now() - ($1::int * interval '1 day') AND desde < now()`, [dias]);
  return json(res, 200, { dias, porDia: porDia.rows.map(r => ({ ...r, horas: Number(r.horas) })), porSector: porSector.rows, resumen: resumen.rows[0] });
}

const celda = (v) => { const t = v instanceof Date ? v.toISOString() : String(v ?? ""); return /[",\n;]/.test(t) ? '"' + t.replace(/"/g, '""') + '"' : t; };

async function exportarCsv(res) {
  const r = await pool.query(
    `SELECT id, equipo, desde, hasta, estado, sector, cliente_caso, cliente, servicio, descripcion_caso, ubicacion, responsable, observacion FROM reservas ORDER BY desde DESC`);
  const cols = ["id","equipo","desde","hasta","estado","sector","cliente_caso","cliente","servicio","descripcion_caso","ubicacion","responsable","observacion"];
  const csv = "\uFEFF" + [cols.join(",")].concat(r.rows.map(f => cols.map(c => celda(f[c])).join(","))).join("\r\n");
  res.writeHead(200, { "Content-Type": "text/csv; charset=utf-8", "Content-Disposition": 'attachment; filename="reservas-veex.csv"', "Cache-Control": "no-store" });
  res.end(csv);
}

async function api(req, res, url) {
  if (req.method === "GET" && url.pathname === "/api/estadisticas") return estadisticas(res, url);
  if (req.method === "GET" && url.pathname === "/api/reservas.csv") return exportarCsv(res);
  const m = url.pathname.match(/^\/api\/reservas(?:\/(\d+)\/(estado|extender))?$/);
  if (!m) return json(res, 404, { error: "no existe" });

  if (req.method === "GET" && !m[1]) {
    const r = await pool.query(
      `SELECT id, equipo, desde, hasta, sector, cliente_caso, cliente, servicio, descripcion_caso, ubicacion, responsable, observacion, estado
       FROM reservas
       WHERE estado IN ('reservado','retirado') OR hasta > now() - interval '7 days'
       ORDER BY desde`
    );
    return json(res, 200, { ahora: new Date().toISOString(), reservas: r.rows });
  }

  if (req.method === "POST" && !m[1]) {
    const b = await leerBody(req);
    const desde = fecha(b.desde), hasta = fecha(b.hasta);
    if (!EQUIPOS.includes(b.equipo)) return json(res, 400, { error: "Elegí el equipo." });
    if (!desde || !hasta) return json(res, 400, { error: "Completá desde y hasta." });
    if (hasta <= desde) return json(res, 400, { error: "'Hasta' tiene que ser posterior a 'Desde'." });
    if (!txt(b.responsable, 80)) return json(res, 400, { error: "Indicá el responsable." });
    try {
      const r = await pool.query(
        `INSERT INTO reservas (equipo, desde, hasta, sector, cliente_caso, cliente, servicio, descripcion_caso, ubicacion, responsable, observacion)
         VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11) RETURNING id`,
        [b.equipo, desde, hasta, txt(b.sector, 40), txt(b.cliente_caso), txt(b.cliente), txt(b.servicio), txt(b.descripcion_caso, 1500), txt(b.ubicacion), txt(b.responsable, 80), txt(b.observacion, 1000)]
      );
      return json(res, 201, { id: r.rows[0].id });
    } catch (e) {
      if (e.code === "23P01") return json(res, 409, { error: "Ese horario se superpone con otra reserva de este equipo." });
      throw e;
    }
  }

  if (req.method === "POST" && m[1] && m[2] === "estado") {
    const b = await leerBody(req);
    const nuevo = SALIDA[b.estado];
    if (!nuevo) return json(res, 400, { error: "Estado inválido." });
    // Transiciones válidas: reservado->retirado|cancelado, retirado->devuelto
    const desdeEstado = nuevo === "devuelto" ? "retirado" : "reservado";
    const r = await pool.query(
      `UPDATE reservas SET estado=$1 WHERE id=$2 AND estado=$3 RETURNING id`,
      [nuevo, Number(m[1]), desdeEstado]
    );
    if (!r.rowCount) return json(res, 409, { error: "La reserva ya cambió de estado. Recargá." });
    return json(res, 200, { ok: true });
  }

  if (req.method === "POST" && m[1] && m[2] === "extender") {
    const b = await leerBody(req);
    const hasta = fecha(b.hasta);
    if (!hasta) return json(res, 400, { error: "Fecha inválida." });
    try {
      const r = await pool.query(
        `UPDATE reservas SET hasta=$1 WHERE id=$2 AND estado IN ('reservado','retirado') AND $1 > desde RETURNING id`,
        [hasta, Number(m[1])]
      );
      if (!r.rowCount) return json(res, 409, { error: "No se pudo extender." });
      return json(res, 200, { ok: true });
    } catch (e) {
      if (e.code === "23P01") return json(res, 409, { error: "La extensión se superpone con otra reserva." });
      throw e;
    }
  }
  return json(res, 405, { error: "método no permitido" });
}

const server = http.createServer(async (req, res) => {
  try {
    const url = new URL(req.url, "http://x");
    if (url.pathname === "/health") { res.writeHead(200); return res.end("ok"); }
    if (url.pathname.startsWith("/api/")) return await api(req, res, url);
    const file = path.join(__dirname, "public", "index.html");
    res.writeHead(200, { "Content-Type": "text/html; charset=utf-8" });
    fs.createReadStream(file).pipe(res);
  } catch (e) {
    console.error(e);
    json(res, 500, { error: "Error del servidor." });
  }
});

server.listen(process.env.PORT || 3000, () => console.log("reserva-veex en puerto", process.env.PORT || 3000));
