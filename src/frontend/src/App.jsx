import { Fragment, useEffect, useMemo, useState } from "react";
import { initial, step } from "./game.js";
import "./styles.css";

const SPEEDS = [0.5, 1, 2, 4];
const BASE_MS = 900;
const AREAS = ["bottom", "right", "top", "left"]; // seats A1, B1, A2, B2: partners face each other

// Where things go on the scene image, in % of its width and height (x, y).
// card = where that player's played card lands in the middle of the table.
// If the art changes, this is the only place to adjust.
const SPOT = {
  bottom: { card: [50, 57.6], hand: [49.8, 66.5], tag: [50, 96.5], bubble: [65, 80] },
  right: { card: [54.3, 53], hand: [61.3, 51.9], tag: [81, 60], bubble: [79, 30] },
  top: { card: [50, 48.3], hand: [50.3, 36.7], tag: [50, 4], bubble: [62, 12] },
  left: { card: [45.7, 53], hand: [39.1, 51.5], tag: [19, 60], bubble: [24, 28] },
};
const at = ([x, y]) => ({ left: `${x}%`, top: `${y}%` });

const MANILHAS = new Set(["7D", "AS", "7H", "4C"]);
const pct = (x) => `${Math.round(x * 100)}%`;

function Card({ card, back, area, style }) {
  const cls = ["card", area, back && "back", card?.rank === "JK" && "joker"].filter(Boolean).join(" ");
  if (back) return <span className={cls} style={style} />;
  if (card.rank === "JK") return <span className={cls} style={style}>JOKER</span>;
  const file = MANILHAS.has(card.rank) ? `m_${card.rank}` : `${card.rank}_${card.suit}`;
  return <img className={cls} style={style} src={`/cards/${file}.png`} alt={card.rank} title={card.rank === "4C" ? "Zap" : card.rank} />;
}

function Thought({ th }) {
  const hasChance = th.win_chance != null;
  const what = [th.decision, th.card, th.response].filter(Boolean).join(" ");
  return (
    <div className="thought" title={th.beliefs ? JSON.stringify(th.beliefs) : ""}>
      {hasChance && (
        <div className="bar">
          <i style={{ width: pct(th.win_chance) }} />
          <b style={{ left: pct(th.raise_threshold) }} />
        </div>
      )}
      <small>{what}{hasChance && ` · chance ${pct(th.win_chance)} · limiar ${pct(th.raise_threshold)}`}</small>
    </div>
  );
}

function Mind({ seat, st }) {
  const talk = st.talk?.[seat.jid];
  const th = st.thoughts[seat.jid];
  return (
    <section className={`mind team${seat.team}`}>
      <h3>{seat.seat} <span>{seat.personality}</span></h3>
      {talk && <p className="talk">conversa: <em className={talk.action}>{talk.action}{talk.value && ` ${talk.value}`}</em></p>}
      {th && <Thought th={th} />}
    </section>
  );
}

export default function App() {
  const [events, setEvents] = useState([]);
  const [cursor, setCursor] = useState(0);
  const [playing, setPlaying] = useState(true);
  const [speed, setSpeed] = useState(1);
  const [showHands, setShowHands] = useState(true);

  useEffect(() => {
    const ws = new WebSocket(`${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/ws`);
    ws.onmessage = (m) => {
      const ev = JSON.parse(m.data);
      if (ev.event === "match-config") { setEvents([ev]); setCursor(0); }
      else setEvents((prev) => [...prev, ev]);
    };
    return () => ws.close();
  }, []);

  useEffect(() => {
    if (!playing || cursor >= events.length) return;
    const t = setTimeout(() => setCursor((c) => c + 1), BASE_MS / speed);
    return () => clearTimeout(t);
  }, [playing, cursor, events.length, speed]);

  const st = useMemo(() => events.slice(0, cursor).reduce(step, initial), [events, cursor]);
  const newMatch = () => fetch("/match", { method: "POST", headers: { "Content-Type": "application/json" }, body: "{}" });

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
        </div>
        <div className="controls">
          <button onClick={newMatch}>Nova partida</button>
          <button onClick={() => setPlaying(!playing)}>{playing ? "Pausar" : "Continuar"}</button>
          <button onClick={() => setCursor((c) => Math.min(c + 1, events.length))}>Próximo evento</button>
          <button onClick={() => setCursor(events.length)}>Ir ao vivo</button>
          <select value={speed} onChange={(e) => setSpeed(Number(e.target.value))} aria-label="Velocidade">
            {SPEEDS.map((v) => <option key={v} value={v}>{v}×</option>)}
          </select>
        </div>
      </header>

      {st.error && <p className="error">A partida falhou: {st.error}</p>}
      {st.seats.length === 0 && !st.error && <p className="empty">Nenhuma partida em andamento. Clique em “Nova partida”.</p>}

      {st.seats.length > 0 && (
        <main>
          <div className="scene">
            <img className="bg" src="/table.png" alt="Quatro jogadores em volta da mesa de truco" />
            <div className="mat" />
            {st.seats.map((seat, i) => {
              const spot = SPOT[AREAS[i]];
              const hand = st.hands[seat.jid] ?? [];
              return (
                <Fragment key={seat.jid}>
                  <div className="hand-mat" style={at(spot.hand)} />
                  <div className="fan" style={at(spot.hand)}>
                    {hand.map((c, k) => (
                      <Card key={`${c.rank}${c.suit}${k}`} card={c} back={!showHands} style={{ "--r": `${(k - (hand.length - 1) / 2) * 7}deg` }} />
                    ))}
                  </div>
                </Fragment>
              );
            })}
            {st.seats.map((seat, i) => {
              const area = AREAS[i];
              const spot = SPOT[area];
              const played = st.table[seat.jid];
              return (
                <Fragment key={seat.jid}>
                  {played && <Card key={st.tableSeq[seat.jid]} card={played} area={area} style={at(spot.card)} />}
                  <span className={`tag team${seat.team}`} style={at(spot.tag)}>{seat.seat} {seat.personality}</span>
                  {st.bubbles[seat.jid] && <span key={st.bubbles[seat.jid]} className="bubble" style={at(spot.bubble)}>{st.bubbles[seat.jid]}</span>}
                </Fragment>
              );
            })}
          </div>
          <aside>
            <h2>Raciocínio</h2>
            <label className="toggle"><input type="checkbox" checked={showHands} onChange={(e) => setShowHands(e.target.checked)} /> Mostrar mãos</label>
            {st.seats.map((seat) => <Mind key={seat.jid} seat={seat} st={st} />)}
            <h2>Eventos</h2>
            <ol>{st.log.slice().reverse().map((l, i) => <li key={i}>{l}</li>)}</ol>
          </aside>
        </main>
      )}
    </div>
  );
}
