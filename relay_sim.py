"""Núcleo de simulação de comando elétrico (lógica de contatos), independente de UI.
Modelo: nós ligados por componentes de 2 terminais.
  - chave  (NA/NF): fecha/abre a ligação entre dois nós, conforme estado.
  - bobina/lâmpada: carga; energizada se um lado está no nó de +V e o outro no de COM.
  - contato: chave cujo estado vem da bobina de mesma tag (NA segue, NF inverte).
Varredura: a cada ciclo os contatos usam o estado das bobinas do ciclo anterior (como um CLP).
"""

class Circuit:
    def __init__(self, plus="P", common="N"):
        self.plus, self.common = plus, common
        self.parts = []          # dicts: kind, tag, a, b
        self.coil = {}           # tag -> bool
        self.inputs = {}         # tag -> bool (botão acionado / chave ligada)

    def add(self, kind, tag, a, b):
        # kind: 'NA' | 'NF' (botão/chave manual) | 'CNA' | 'CNF' (contato de bobina) | 'coil' | 'lamp'
        self.parts.append(dict(kind=kind, tag=tag, a=a, b=b))
        if kind == "coil":
            self.coil.setdefault(tag, False)
        if kind in ("NA", "NF"):
            self.inputs.setdefault(tag, False)

    def _closed(self, p, coil):
        k = p["kind"]
        if k == "NA":  return self.inputs[p["tag"]]
        if k == "NF":  return not self.inputs[p["tag"]]
        if k == "CNA": return coil.get(p["tag"], False)
        if k == "CNF": return not coil.get(p["tag"], False)
        return False

    def _nets(self, coil):
        par = {}
        def f(x):
            par.setdefault(x, x)
            while par[x] != x:
                par[x] = par[par[x]]; x = par[x]
            return x
        for p in self.parts:
            f(p["a"]); f(p["b"])
            if p["kind"] in ("NA", "NF", "CNA", "CNF") and self._closed(p, coil):
                par[f(p["a"])] = f(p["b"])
        return f

    def step(self):
        f = self._nets(self.coil)
        if f(self.plus) == f(self.common):
            raise RuntimeError("CURTO-CIRCUITO entre +V e COM")
        new, lamps = {}, {}
        for p in self.parts:
            if p["kind"] in ("coil", "lamp"):
                on = {f(p["a"]), f(p["b"])} == {f(self.plus), f(self.common)}
                (new if p["kind"] == "coil" else lamps)[p["tag"]] = on
        changed = new != self.coil
        self.coil = new
        self.lamps = lamps
        return changed

    def settle(self, max_iter=50):
        for _ in range(max_iter):
            if not self.step():
                return
        raise RuntimeError("Não estabiliza (oscilação): revisar intertravamentos")

    def set(self, tag, value):
        self.inputs[tag] = value
        self.settle()

    def state(self):
        return dict(coils=dict(self.coil), lamps=dict(getattr(self, "lamps", {})))


def selo_liga_desliga():
    c = Circuit()
    c.add("NF", "S1", "P", "a")      # Desliga
    c.add("NA", "S2", "a", "b")      # Liga
    c.add("CNA", "K1", "a", "b")     # selo
    c.add("coil", "K1", "b", "N")
    c.add("lamp", "H1", "b", "N")
    c.settle()
    return c


if __name__ == "__main__":
    c = selo_liga_desliga()
    assert not c.coil["K1"]
    c.set("S2", True);  assert c.coil["K1"] and c.lamps["H1"]        # liga
    c.set("S2", False); assert c.coil["K1"]                          # selo mantém
    c.set("S1", True);  assert not c.coil["K1"]                      # desliga
    c.set("S1", False); assert not c.coil["K1"]                      # permanece off
    # botão Liga com Desliga pressionado não liga
    c.set("S1", True); c.set("S2", True); assert not c.coil["K1"]
    print("OK: selo, desligamento e prioridade do desliga")

    # curto-circuito detectado
    d = Circuit(); d.add("NA", "X", "P", "N"); d.inputs["X"] = True
    try: d.step(); print("FALHA: curto não detectado")
    except RuntimeError as e: print("OK:", e)
