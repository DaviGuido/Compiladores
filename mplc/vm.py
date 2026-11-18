"""VM de pilha com um registro de ativacao (locais e pilha) por chamada."""
import json
import math
from mplc.erros import ErroMPL


class VM:
    def __init__(self, instrucoes, saida):
        self.ins = instrucoes
        self.saida = saida
        self.funcoes = {}
        self.max_profundidade = 120
        self._indexar()

    def _indexar(self):
        atual = None
        for i, ins in enumerate(self.ins):
            if ins['op'] == 'FUNC':
                atual = {'inicio': i + 1, 'fim': None,
                         'parametros': ins['parametros'], 'tipo': ins['tipo']}
                self.funcoes[ins['nome']] = atual
            elif ins['op'] == 'END' and atual is not None:
                atual['fim'] = i
                atual = None

    @staticmethod
    def _padrao(tipo):
        return {'inteiro': 0, 'real': 0.0, 'logico': False, 'texto': ''}[tipo]

    @staticmethod
    def _trunc_div(a, b):
        if b == 0: raise ZeroDivisionError
        return math.trunc(a / b)

    @staticmethod
    def _resto(a, b):
        if b == 0: raise ZeroDivisionError
        return a - math.trunc(a / b) * b

    @staticmethod
    def _formatar(v):
        if isinstance(v, bool): return 'verdadeiro' if v else 'falso'
        if isinstance(v, float): return f'{v:.6f}'
        return str(v)

    def _erro(self, linha, mensagem):
        raise ErroMPL('execucao', linha or 1, 1, mensagem)

    def chamar(self, nome, argumentos, profundidade=0, linha_chamada=1):
        if profundidade >= self.max_profundidade:
            self._erro(linha_chamada, 'estouro de pilha')
        if nome not in self.funcoes:
            self._erro(linha_chamada, f'funcao inexistente: {nome}')
        info = self.funcoes[nome]
        if len(argumentos) != len(info['parametros']):
            self._erro(linha_chamada, f'quantidade invalida de argumentos em {nome}')
        # Registro de ativacao isolado: parametros, locais e pilha de operandos.
        locais = dict(zip(info['parametros'], argumentos))
        pilha = []
        labels = {}
        for pc in range(info['inicio'], info['fim']):
            if self.ins[pc]['op'] == 'LABEL': labels[self.ins[pc]['nome']] = pc
        pc = info['inicio']
        while pc < info['fim']:
            ins = self.ins[pc]; op = ins['op']; linha = ins.get('linha', 1)
            try:
                if op == 'PUSH': pilha.append(ins['valor'])
                elif op == 'DEFAULT': locais[ins['slot']] = self._padrao(ins['tipo'])
                elif op == 'LOAD': pilha.append(locais.get(ins['slot'], 0))
                elif op == 'STORE': locais[ins['slot']] = pilha.pop()
                elif op == 'CAST_REAL': pilha.append(float(pilha.pop()))
                elif op == 'UNARY':
                    a = pilha.pop()
                    pilha.append((not a) if ins['operador'] == 'nao' else -a)
                elif op == 'BINARY':
                    b = pilha.pop(); a = pilha.pop(); oper = ins['operador']
                    if oper == '+': v = a + b
                    elif oper == '-': v = a - b
                    elif oper == '*': v = a * b
                    elif oper == '/': v = self._trunc_div(a, b) if isinstance(a, int) and not isinstance(a, bool) and isinstance(b, int) and not isinstance(b, bool) else a / b
                    elif oper == '%': v = self._resto(a, b)
                    elif oper == '==': v = a == b
                    elif oper == '!=': v = a != b
                    elif oper == '<': v = a < b
                    elif oper == '<=': v = a <= b
                    elif oper == '>': v = a > b
                    elif oper == '>=': v = a >= b
                    elif oper == 'e': v = bool(a) and bool(b)
                    elif oper == 'ou': v = bool(a) or bool(b)
                    else: self._erro(linha, f'operador desconhecido: {oper}')
                    pilha.append(v)
                elif op == 'PRINT': self.saida.write(self._formatar(pilha.pop()) + '\n')
                elif op == 'JZ':
                    if not pilha.pop(): pc = labels[ins['destino']]
                elif op == 'JMP': pc = labels[ins['destino']]
                elif op == 'CALL':
                    qtd = ins['quantidade']
                    args = pilha[-qtd:] if qtd else []
                    if qtd: del pilha[-qtd:]
                    resultado = self.chamar(ins['funcao'], args, profundidade + 1, linha)
                    if ins.get('tipo') != 'vazio': pilha.append(resultado)
                elif op == 'RET': return pilha.pop() if ins.get('tem_valor') else None
                elif op in ('LABEL',): pass
                else: self._erro(linha, f'instrucao desconhecida: {op}')
            except ZeroDivisionError:
                self._erro(linha, 'divisao ou resto por zero')
            except IndexError:
                self._erro(linha, 'pilha de operandos inconsistente')
            pc += 1
        return None


def executar(texto_mplb, saida):
    try:
        instrucoes = [json.loads(linha) for linha in texto_mplb.splitlines() if linha.strip()]
    except (json.JSONDecodeError, TypeError) as e:
        raise ErroMPL('execucao', 1, 1, f'bytecode invalido: {e}')
    maquina = VM(instrucoes, saida)
    if 'principal' not in maquina.funcoes:
        raise ErroMPL('execucao', 1, 1, "funcao 'principal' ausente")
    maquina.chamar('principal', [])
