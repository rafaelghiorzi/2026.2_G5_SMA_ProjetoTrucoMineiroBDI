import { Fragment, useEffect, useMemo, useState } from "react";
import { CALL_NAMES, CATEGORY, initial, nextLevel, step } from "./game.js";
import "./styles.css";

const SPEEDS = [0.5, 1, 2, 4];
const BASE_MS = 900;
// Not every event deserves a full beat: a thought only refreshes a box, and the person's own events are instant
const BEAT = { thought: 0.25, prompt: 0, "prompt-done": 0, "human-talk": 0, "human-reading": 0 };
const RECONNECT_MS = 1000;
const SEAT_NAMES = ["A1", "B1", "A2", "B2"];
const AREAS = ["bottom", "right", "top", "left"]; // seats A1, B1, A2, B2: partners face each other

// Where things go on the scene image, in % of its width and height (x, y).
// mind = which edges of the image that player's thinking box is pinned to (in %). It grows inward from there, so it is never cut off.
// The speech bubble hangs off the box (below a top box, above a bottom one), so it is always next to whoever is talking;
// it may cover part of the table as long as it stays off the cards and the players.
// card = where that player's played card lands on the felt; hand = the fan of cards on the felt in front of them.
// Everything on the felt stays inside the green oval (about x 35-65%, y 31-73%) so no card covers a player or the wood.
// If the art changes, this is the only place to adjust.
const SPOT = {
  bottom: { card: [50.3, 58.5], hand: [50.2, 67.5], mind: { left: 1, bottom: 2 }, tag: [50, 94] },
  right: { card: [55.3, 54], hand: [61.4, 53.3], mind: { right: 1, bottom: 2 }, tag: [79, 53] },
  top: { card: [49.7, 48.3], hand: [50.2, 38.5], mind: { right: 1, top: 2 }, tag: [50, 5] },
  left: { card: [44.7, 53], hand: [38.8, 53.3], mind: { left: 1, top: 2 }, tag: [21, 53] },
};
// Seat tag (A1, B2...): by default it sits beyond each hand, away from the table centre, i.e. next to the player.
// To place one by hand, add tag: [x, y] to that seat in SPOT.
const CENTER = [50, 53.5];
const tagPos = ({ tag, hand }) => tag ?? hand.map((v, i) => Math.max(4, Math.min(96, CENTER[i] + (v - CENTER[i]) * 2.2)));
const at = ([x, y]) => ({ left: `${x}%`, top: `${y}%` });
const pin = (edges) => Object.fromEntries(Object.entries(edges).map(([k, v]) => [k, `${v}%`]));

const MANILHAS = new Set(["7D", "AS", "7H", "4C"]);
const pct = (x) => `${Math.round(x * 100)}%`;

function Card({ card, back, area, style }) {
  const cls = ["card", area, back && "back", card?.rank === "JK" && "joker"].filter(Boolean).join(" ");
  if (back) return <span className={cls} style={style} />;
  if (card.rank === "JK") return <span className={cls} style={style}>JOKER</span>;
  const file = MANILHAS.has(card.rank) ? `m_${card.rank}` : `${card.rank}_${card.suit}`;
  return <img className={cls} style={style} src={`/cards/${file}.png`} alt={card.rank} title={card.rank === "4C" ? "Zap" : card.rank} />;
}

const fmt = (x) => (x == null ? "–" : Number(x).toFixed(2));
// Strengths go from 0 to 1 (power = (position / 11) ** 1.5). The ticks mark WEAK_BELOW and STRONG_FROM from config.py.
const WEAK_BELOW = 0.35, STRONG_FROM = 0.6;

function Strength({ label, value }) {
  const v = value == null ? 0 : Math.max(0, Math.min(1, Number(value)));
  return (
    <div className="row">
      <span>{label}</span>
      <div className="bar">
        <i style={{ width: pct(v) }} />
        <u style={{ left: pct(WEAK_BELOW) }} />
        <u style={{ left: pct(STRONG_FROM) }} />
      </div>
      <strong>{fmt(value)}</strong>
    </div>
  );
}

function Thought({ th, names }) {
  const who = (jid) => names[jid] ?? jid;
  const what = [th.decision, th.card, th.response].filter(Boolean).join(" ");
  const partner = Object.entries(th.beliefs_about_partner ?? {});
  const opponents = Object.entries(th.beliefs_about_opponents ?? {});
  return (
    <div className="thought">
      <Strength label="Minha mão" value={th.own_strength} />
      {partner.map(([jid, v]) => <Strength key={jid} label={`Parceiro ${who(jid)}`} value={v} />)}
      {opponents.map(([jid, v]) => <Strength key={jid} label={`Oponente ${who(jid)}`} value={v} />)}
      {th.win_chance != null && (
        <div className="row chance" title={`limiar para aumentar: ${pct(th.raise_threshold)}`}>
          <span>Chance de ganhar</span>
          <div className="bar">
            <i style={{ width: pct(th.win_chance) }} />
            <b style={{ left: pct(th.raise_threshold) }} />
          </div>
          <strong>{pct(th.win_chance)}</strong>
        </div>
      )}
      <p className="what">{what}</p>
    </div>
  );
}

const TALK_NAMES = { send: "enviar sinal", listen: "ouvir", spy: "espiar", bluff: "blefar", nothing: "nada" };

// reveal = false hides what this player would keep to themselves (talk action and reasoning)
function Mind({ seat, st, style, side, reveal }) {
  const bubble = st.bubbles[seat.jid];
  const talk = st.talk?.[seat.jid];
  const th = st.thoughts[seat.jid];
  return (
    <section className={`mind team${seat.team}`} style={style}>
      <h3><b className="seat">{seat.seat}</b> <span>{seat.personality}</span></h3>
      {reveal && talk && <p className="talk">conversa: <em className={talk.action}>{talk.action}{talk.value && ` ${talk.value}`}</em></p>}
      {bubble && <span key={bubble} className={`bubble ${side}`}>{bubble}</span>}
      {reveal && (th ? <Thought th={th} names={st.names} /> : <p className="wait">aguardando decisão</p>)}
    </section>
  );
}

function HumanMind({ seat, st, style, side }) {
  const bubble = st.bubbles[seat.jid];
  const mine = st.myTalk;
  const partner = st.seats[(st.seats.indexOf(seat) + 2) % 4].jid;
  return (
    <section className={`mind team${seat.team}`} style={style}>
      <h3><b className="seat">{seat.seat}</b> <span>Você</span></h3>
      {mine && (
        <p className="talk">conversa: <em className={mine.action}>
          {TALK_NAMES[mine.action]}{mine.value && ` (${CATEGORY[mine.value]})`}{mine.spy_failed && " · falhou"}
        </em></p>
      )}
      {st.heard.map((sig) => (
        <p key={sig.from} className="heard">
          {sig.from === partner ? "parceiro" : "oponente"} {st.names[sig.from]}: mão <strong>{CATEGORY[sig.value]}</strong>
        </p>
      ))}
      {bubble && <span key={bubble} className={`bubble ${side}`}>{bubble}</span>}
    </section>
  );
}

// What the person is being asked. Clicking posts the choice; the server checks it again.
function Prompt({ prompt, st, me, onChoose, busy }) {
  const who = (jid) => st.names[jid] ?? jid;
  const art = (rank) => (st.hands[me.jid] ?? []).find((c) => c.rank === rank) ?? { rank, suit: "S" };
  const choose = (choice) => onChoose({ kind: prompt.kind, ...choice });
  if (prompt.kind === "turn") {
    const call = nextLevel(st.bet);
    return (
      <div className="act">
        <p>Sua vez: escolha uma carta{prompt.can_call && " ou peça aumento"}.</p>
        <div className="choices">
          {prompt.hand.map((rank, k) => (
            <button key={`${rank}${k}`} className="pick" disabled={busy} onClick={() => choose({ card: rank })}>
              <Card card={art(rank)} />
            </button>
          ))}
          {prompt.can_call && call && (
            <button className="loud" disabled={busy} onClick={() => choose({ call: true })}>{CALL_NAMES[call].toUpperCase()}!</button>
          )}
        </div>
      </div>
    );
  }
  if (prompt.kind === "response") {
    const caller = st.call?.player;
    const raise = nextLevel(prompt.value);
    return (
      <div className="act">
        <p>{caller ? who(caller) : "O oponente"} pediu <strong>{CALL_NAMES[prompt.value]}</strong>. O que você responde?</p>
        <div className="choices">
          <button disabled={busy} onClick={() => choose({ response: "fold" })}>Corro</button>
          <button disabled={busy} onClick={() => choose({ response: "accept" })}>Aceito</button>
          {prompt.can_raise && (
            <button className="loud" disabled={busy} onClick={() => choose({ response: "raise" })}>{CALL_NAMES[raise].toUpperCase()}!</button>
          )}
        </div>
      </div>
    );
  }
  return (
    <div className="act">
      <p>Conversa do ponto: sua mão é <strong>{CATEGORY[prompt.category]}</strong>. O que você faz?</p>
      <div className="choices">
        <button disabled={busy} onClick={() => choose({ action: "send" })} title="Seu parceiro recebe a categoria real da sua mão">Enviar sinal</button>
        <button disabled={busy} onClick={() => choose({ action: "listen" })} title="Confia mais no sinal do parceiro">Ouvir</button>
        <button disabled={busy} onClick={() => choose({ action: "spy" })} title="Pode falhar; se der certo, ouve o que os oponentes enviaram (inclusive blefes)">Espiar</button>
        {prompt.bluffs.map((c) => (
          <button key={c} className="bluff" disabled={busy} onClick={() => choose({ action: "bluff", value: c })} title="Só quem espiar recebe">
            Blefar mão {CATEGORY[c]}
          </button>
        ))}
        <button disabled={busy} onClick={() => choose({ action: "nothing" })}>Nada</button>
      </div>
    </div>
  );
}

export default function App() {
  const [events, setEvents] = useState([]);
  const [cursor, setCursor] = useState(0);
  const [playing, setPlaying] = useState(true);
  const [speed, setSpeed] = useState(1);
  const [showHands, setShowHands] = useState(true);
  const [connected, setConnected] = useState(false);
  const [seat, setSeat] = useState("");
  const [starting, setStarting] = useState(false);
  const [sent, setSent] = useState(null); // seq of the prompt already answered, until the server confirms
  const [notice, setNotice] = useState(null);

  // The backend takes a few seconds to come up (XMPP server + agents), and the page may
  // open before it: keep trying until it answers, and again whenever the connection drops.
  useEffect(() => {
    let ws, retry, closed = false;
    const connect = () => {
      ws = new WebSocket(`${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/ws`);
      ws.onopen = () => setConnected(true);
      ws.onmessage = (m) => {
        const ev = JSON.parse(m.data);
        if (ev.event === "history") {
          // What already happened is shown as it is now, not replayed as a match that is just starting
          setEvents(ev.events); setCursor(ev.events.length);
        } else if (ev.event === "match-config") { setEvents([ev]); setCursor(0); setStarting(false); }
        else setEvents((prev) => [...prev, ev]);
      };
      ws.onclose = () => {
        setConnected(false);
        if (!closed) retry = setTimeout(connect, RECONNECT_MS);
      };
    };
    connect();
    return () => { closed = true; clearTimeout(retry); ws.close(); };
  }, []);

  useEffect(() => {
    if (!playing || cursor >= events.length) return;
    const t = setTimeout(() => setCursor((c) => c + 1), (BASE_MS * (BEAT[events[cursor].event] ?? 1)) / speed);
    return () => clearTimeout(t);
  }, [playing, cursor, events, speed]);

  const st = useMemo(() => events.slice(0, cursor).reduce(step, initial), [events, cursor]);
  const me = st.seats.find((x) => x.human);
  const reveal = !me || showHands;
  const offset = me ? st.seats.indexOf(me) : 0; // whoever plays sits at the bottom

  // Playing, the agents' hands and minds start hidden; watching, everything starts open
  useEffect(() => setShowHands(!me), [me?.jid]);

  const post = async (path, body) => {
    const r = await fetch(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
    if (!r.ok) throw new Error((await r.json().catch(() => null))?.detail ?? `erro ${r.status}`);
    return r.json();
  };

  const newMatch = async () => {
    setStarting(true); setNotice(null); setSent(null);
    try {
      await post("/match", { seat: seat || null });
    } catch (e) {
      setStarting(false); setNotice(`Não foi possível iniciar: ${e.message}`);
    }
  };

  const choose = async (choice) => {
    setSent(st.prompt.seq); setNotice(null);
    try {
      await post("/action", choice);
    } catch (e) {
      setSent(null); setNotice(e.message);
    }
  };

  return (
    <div className="app">
      <header>
        <div className="score">
          <span className="plaque teamA">Time A <strong>{st.score.A}</strong></span>
          <span className="plaque teamB">Time B <strong>{st.score.B}</strong></span>
        </div>
        <div className="meta">
          {st.point > 0 && `Ponto ${st.point}`}
          {st.bet > 1 && ` · valendo ${st.bet}`}
          {st.rounds.length > 0 && ` · rodadas ${st.rounds.map((r) => r ?? "–").join(" ")}`}
          {st.over && " · fim de partida"}
          {st.seed != null && <small> · seed {st.seed}</small>}
        </div>
        <div className="controls">
          <span className={`link ${connected ? "on" : "off"}`}>{connected ? "conectado" : "conectando…"}</span>
          <select value={seat} onChange={(e) => setSeat(e.target.value)} aria-label="Assento">
            <option value="">Assistir</option>
            {SEAT_NAMES.map((name) => <option key={name} value={name}>Jogar como {name}</option>)}
          </select>
          <button onClick={newMatch} disabled={!connected || starting}>{starting ? "Iniciando…" : "Nova partida"}</button>
          <button onClick={() => setPlaying(!playing)}>{playing ? "Pausar" : "Continuar"}</button>
          <button onClick={() => setCursor((c) => Math.min(c + 1, events.length))}>Próximo evento</button>
          <button onClick={() => setCursor(events.length)}>Ir ao vivo</button>
          <label className="toggle"><input type="checkbox" checked={showHands} onChange={(e) => setShowHands(e.target.checked)} /> {me ? "Revelar agentes" : "Mostrar mãos"}</label>
          <select value={speed} onChange={(e) => setSpeed(Number(e.target.value))} aria-label="Velocidade">
            {SPEEDS.map((v) => <option key={v} value={v}>{v}×</option>)}
          </select>
        </div>
      </header>

      {notice && <p className="error">{notice}</p>}
      {st.error && <p className="error">A partida falhou: {st.error}</p>}
      {st.seats.length === 0 && !st.error && (
        <p className="empty">
          {!connected ? "Conectando ao servidor… (o backend leva alguns segundos para subir)"
            : starting ? "Iniciando partida…" : "Nenhuma partida em andamento. Escolha assistir ou jogar e clique em “Nova partida”."}
        </p>
      )}

      {st.seats.length > 0 && (
        <main>
          <div className="scene">
            <img className="bg" src="/table.png" alt="Quatro jogadores em volta da mesa de truco" />
            {st.seats.map((seat, i) => {
              const area = AREAS[(i - offset + 4) % 4];
              const spot = SPOT[area];
              const hand = st.hands[seat.jid] ?? [];
              const open = seat.human || reveal;
              return (
                <Fragment key={seat.jid}>
                  <div className={`fan ${area}`} style={at(spot.hand)}>
                    {hand.map((c, k) => (
                      <Card key={`${c.rank}${c.suit}${k}`} card={c} back={!open} style={{ "--r": `${(k - (hand.length - 1) / 2) * 7}deg` }} />
                    ))}
                  </div>
                </Fragment>
              );
            })}
            {st.seats.map((seat, i) => {
              const area = AREAS[(i - offset + 4) % 4];
              const spot = SPOT[area];
              const played = st.table[seat.jid];
              const side = spot.mind.top != null ? "below" : "above";
              return (
                <Fragment key={seat.jid}>
                  {played && <Card key={st.tableSeq[seat.jid]} card={played} area={area} style={at(spot.card)} />}
                  <span className={`tag team${seat.team}`} style={at(tagPos(spot))}>{seat.seat}</span>
                  {seat.human
                    ? <HumanMind seat={seat} st={st} style={pin(spot.mind)} side={side} />
                    : <Mind seat={seat} st={st} style={pin(spot.mind)} side={side} reveal={reveal} />}
                </Fragment>
              );
            })}
          </div>
          {me && st.prompt && !starting && <Prompt prompt={st.prompt} st={st} me={me} onChoose={choose} busy={sent === st.prompt.seq} />}
        </main>
      )}
    </div>
  );
}
