// Pure reducer: (state, event) -> state. The UI replays the events up to a cursor,
// so pause, step and "live" are just a different cursor.

export const CALL_NAMES = { 3: "truco", 6: "seis", 9: "nove", 12: "doze" };
const CATEGORY = { weak: "fraca", medium: "média", strong: "forte" };
const ANSWER = { fold: "Corro!", accept: "Aceito!", raise: "Aumento!" };

// The table only sends ranks, so suits are just art. Spread them so the same face
// never shows twice in a deal. Manilhas and the joker have a single face.
const SUITS = { Q: "SHCD", J: "SHCD", K: "SHCD", "2": "SHCD", "3": "SHCD", A: "D" };
const POWER = { Q: 1, J: 2, K: 3, A: 4, "2": 5, "3": 6, JK: 7, "7D": 8, AS: 9, "7H": 10, "4C": 11 };

function deal(hands) {
  const used = {};
  return Object.fromEntries(Object.entries(hands).map(([jid, ranks]) => [
    jid,
    ranks
      .map((rank) => {
        const suits = SUITS[rank];
        const suit = suits ? suits[(used[rank] = (used[rank] ?? -1) + 1) % suits.length] : null;
        return { rank, suit };
      })
      .sort((a, b) => POWER[a.rank] - POWER[b.rank]),
  ]));
}

export const initial = {
  seats: [], names: {}, score: { A: 0, B: 0 }, point: 0,
  hands: {}, table: {}, tableSeq: {}, roundDone: false, rounds: [], bet: 1,
  call: null, talk: null, decl: {}, thoughts: {}, bubbles: {}, log: [], over: false, error: null,
};

export function step(s, ev) {
  const n = (jid) => s.names[jid] ?? jid;
  const say = (text) => ({ log: [...s.log.slice(-60), text] });
  const bubble = (jid, text) => ({ ...s.bubbles, [jid]: text });

  switch (ev.event) {
    case "match-config":
      return { ...initial, seats: ev.seats, names: Object.fromEntries(ev.seats.map((x) => [x.jid, x.seat])) };
    case "match-error":
      return { ...s, error: ev.message };
    case "new-point":
      return {
        ...s, point: ev.point, hands: deal(ev.hands), score: ev.score, table: {}, tableSeq: {}, roundDone: false,
        rounds: [], bet: 1, call: null, talk: null, decl: {}, thoughts: {}, bubbles: {}, ...say(`Ponto ${ev.point} começou`),
      };
    case "talk-log":
      return {
        ...s, talk: ev.declarations,
        ...say("Conversa: " + Object.entries(ev.declarations).map(([j, d]) => `${n(j)} ${d.action}`).join(", ")),
      };
    case "thought":
      return { ...s, thoughts: { ...s.thoughts, [ev.player]: ev } };
    case "card-played": {
      const hand = [...(s.hands[ev.player] ?? [])];
      const i = hand.findIndex((c) => c.rank === ev.card);
      const [played] = i >= 0 ? hand.splice(i, 1) : [{ rank: ev.card, suit: SUITS[ev.card]?.[0] ?? null }];
      const { [ev.player]: _gone, ...bubbles } = s.bubbles;
      return {
        ...s, hands: { ...s.hands, [ev.player]: hand }, bubbles, roundDone: false,
        table: { ...(s.roundDone ? {} : s.table), [ev.player]: played },
        tableSeq: { ...(s.roundDone ? {} : s.tableSeq), [ev.player]: ev.seq },
        ...say(`${n(ev.player)} jogou ${ev.card}`),
      };
    }
    case "call":
      return {
        ...s, call: { player: ev.player, value: ev.value, responder: ev.responder, response: null },
        bubbles: bubble(ev.player, `${(CALL_NAMES[ev.value] ?? ev.value).toUpperCase()}!`),
        ...say(`${n(ev.player)} pediu ${CALL_NAMES[ev.value] ?? ev.value}`),
      };
    case "declaration":
      return {
        ...s, decl: { ...s.decl, [ev.player]: ev.category },
        bubbles: bubble(ev.player, `Mão ${CATEGORY[ev.category] ?? ev.category}`),
        ...say(`${n(ev.player)} declarou mão ${ev.category}`),
      };
    case "response":
      return {
        ...s, call: s.call && { ...s.call, response: ev.response },
        bet: ev.response === "accept" ? ev.value : s.bet,
        bubbles: bubble(ev.player, ANSWER[ev.response] ?? ev.response),
        ...say(`${n(ev.player)}: ${ev.response}`),
      };
    case "round-end":
      return { ...s, roundDone: true, rounds: [...s.rounds, ev.winner], ...say(`Rodada: ${ev.winner ?? "empate"}`) };
    case "point-end":
      return { ...s, score: ev.score, call: null, ...say(`Ponto para ${ev.winner ?? "ninguém"} (+${ev.points})`) };
    case "match-end":
      return { ...s, score: ev.score, over: true, ...say("Fim da partida") };
    default:
      return s;
  }
}
