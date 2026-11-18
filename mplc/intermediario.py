"""Geracao de codigo intermediario de tres enderecos para MPL."""
from dataclasses import dataclass


@dataclass
class Codigo:
    instrucoes: list
    linhas: list


class Tradutor:
    def __init__(self, arvore, tabela):
        self.arvore = arvore
        self.tabela = tabela
        self.ins = []
        self.linhas = []
        self.temp = 0
        self.rotulo = 0
        self.escopos = []
        self.slots = {}

    def novo_temp(self):
        n = f't{self.temp}'
        self.temp += 1
        return n

    def novo_rotulo(self):
        n = f'L{self.rotulo}'
        self.rotulo += 1
        return n

    def emitir(self, op, linha=1, **kw):
        self.ins.append(dict(op=op, linha=linha, **kw))

    def ir(self, texto):
        self.linhas.append(texto)

    def abrir(self):
        self.escopos.append({})

    def fechar(self):
        self.escopos.pop()

    def declarar(self, simbolo):
        slot = f'v{simbolo.escopo}_{simbolo.nome}_{len(self.slots)}'
        self.slots[id(simbolo)] = slot
        self.escopos[-1][simbolo.nome] = slot
        return slot

    def slot_expr(self, no):
        simbolo = no.extra.get('simbolo')
        if simbolo is not None and id(simbolo) in self.slots:
            return self.slots[id(simbolo)]
        nome = no.extra.get('nome') or no.rotulo.split(' ', 1)[-1]
        for escopo in reversed(self.escopos):
            if nome in escopo:
                return escopo[nome]
        raise ValueError(f'local sem endereco: {nome}')

    def converter(self, temp, no):
        if no.extra.get('converter_para') == 'real':
            novo = self.novo_temp()
            self.emitir('CAST', no.linha, destino=novo, origem=temp, tipo='real')
            self.ir(f'{novo} = real {temp}')
            return novo
        return temp

    def expressao(self, no):
        r = no.rotulo
        if r.startswith('literal '):
            tipo = no.extra.get('tipo_semantico') or no.extra.get('tipo') or r.split()[1]
            valor = no.extra.get('valor', r.split(' ', 2)[-1])
            if tipo == 'texto':
                import ast
                valor = ast.literal_eval(valor)
            elif tipo == 'logico':
                valor = valor == 'verdadeiro'
            elif tipo == 'inteiro':
                valor = int(valor)
            elif tipo == 'real':
                valor = float(valor)
            t = self.novo_temp()
            self.emitir('CONST', no.linha, destino=t, valor=valor, tipo=tipo)
            self.ir(f'{t} = {json_valor(valor)}')
            return self.converter(t, no)
        if r.startswith('variavel '):
            slot = self.slot_expr(no)
            t = self.novo_temp()
            self.emitir('LOAD', no.linha, destino=t, slot=slot)
            self.ir(f'{t} = carrega {slot}')
            return self.converter(t, no)
        if r.startswith('chamada '):
            args = [self.expressao(x) for x in no.filhos]
            t = self.novo_temp()
            nome = no.extra.get('nome', r[len('chamada '):])
            self.emitir('CALL', no.linha, destino=t, funcao=nome, argumentos=args, tipo=no.extra.get('tipo_semantico', 'vazio'))
            self.ir(f'{t} = chama {nome} ' + ' '.join(args))
            return self.converter(t, no)
        if r.startswith('unario '):
            a = self.expressao(no.filhos[0])
            t = self.novo_temp(); op = no.extra.get('operador', r[len('unario '):])
            self.emitir('UN', no.linha, destino=t, operador=op, origem=a)
            self.ir(f'{t} = {op} {a}')
            return self.converter(t, no)
        if r.startswith('binario '):
            a = self.expressao(no.filhos[0]); b = self.expressao(no.filhos[1])
            t = self.novo_temp(); op = no.extra.get('operador', r[len('binario '):])
            self.emitir('BIN', no.linha, destino=t, operador=op, esquerda=a, direita=b)
            self.ir(f'{t} = {a} {op} {b}')
            return self.converter(t, no)
        raise ValueError(f'expressao desconhecida: {r}')

    def bloco(self, no, novo=True):
        if novo: self.abrir()
        for cmd in no.filhos: self.comando(cmd)
        if novo: self.fechar()

    def comando(self, no):
        r = no.rotulo; linha = no.linha or 1
        if r == 'bloco':
            self.bloco(no); return
        if r.startswith('declaracao '):
            simbolo = no.extra['simbolo']; slot = self.declarar(simbolo)
            self.emitir('DEFAULT', linha, slot=slot, tipo=simbolo.tipo)
            self.ir(f'{slot} = padrao {simbolo.tipo}')
            if no.filhos:
                v = self.expressao(no.filhos[0]); self.emitir('STORE', linha, slot=slot, origem=v)
                self.ir(f'{slot} = {v}')
            return
        if r.startswith('atribuicao '):
            simbolo = no.extra['simbolo']; slot = self.slots[id(simbolo)]
            v = self.expressao(no.filhos[0]); self.emitir('STORE', linha, slot=slot, origem=v)
            self.ir(f'{slot} = {v}'); return
        if r == 'escreva':
            v = self.expressao(no.filhos[0]); self.emitir('PRINT', linha, origem=v); self.ir(f'escreva {v}'); return
        if r == 'retorne':
            v = self.expressao(no.filhos[0]) if no.filhos else None
            self.emitir('RET', linha, origem=v); self.ir('retorne' + (f' {v}' if v else '')); return
        if r.startswith('chamada '):
            self.expressao(no); return
        if r == 'se':
            cond = self.expressao(no.filhos[0]); senao = self.novo_rotulo(); fim = self.novo_rotulo()
            self.emitir('JZ', linha, condicao=cond, destino=senao); self.ir(f'seFalso {cond} desvie {senao}')
            self.bloco(no.filhos[1]); self.emitir('JMP', linha, destino=fim); self.ir(f'desvie {fim}')
            self.emitir('LABEL', linha, nome=senao); self.ir(f'{senao}:')
            if len(no.filhos) == 3: self.bloco(no.filhos[2])
            self.emitir('LABEL', linha, nome=fim); self.ir(f'{fim}:'); return
        if r == 'enquanto':
            inicio = self.novo_rotulo(); fim = self.novo_rotulo()
            self.emitir('LABEL', linha, nome=inicio); self.ir(f'{inicio}:')
            cond = self.expressao(no.filhos[0]); self.emitir('JZ', linha, condicao=cond, destino=fim); self.ir(f'seFalso {cond} desvie {fim}')
            self.bloco(no.filhos[1]); self.emitir('JMP', linha, destino=inicio); self.ir(f'desvie {inicio}')
            self.emitir('LABEL', linha, nome=fim); self.ir(f'{fim}:'); return
        raise ValueError(f'comando desconhecido: {r}')

    def gerar(self):
        for func in self.arvore.filhos:
            nome = func.extra['nome']; tipo = func.extra['tipo']; params, corpo = func.filhos
            self.temp = 0; self.rotulo = 0; self.slots = {}
            self.ir(f'funcao {nome} {tipo}'); self.emitir('FUNC', func.linha, nome=nome, tipo=tipo, parametros=[])
            self.abrir()
            ps = []
            for p in params.filhos:
                sim = p.extra['simbolo']; slot = self.declarar(sim); ps.append(slot)
            self.ins[-1]['parametros'] = ps
            # O corpo da funcao e um escopo de bloco distinto do de parametros.
            self.bloco(corpo)
            self.emitir('END', func.linha, nome=nome); self.ir('fim')
            self.fechar()
        return Codigo(self.ins, self.linhas)


def json_valor(v):
    import json
    return json.dumps(v, ensure_ascii=False)


def gerar(arvore, tabela):
    return Tradutor(arvore, tabela).gerar()


def despejar(codigo):
    return codigo.linhas
