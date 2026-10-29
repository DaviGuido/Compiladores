"""
Entrega 3 — analise semantica.

Tabela de simbolos, escopos aninhados e verificacao de tipos.

A tabela e organizada em uma lista de escopos, cada qual com seu pai e seus
simbolos locais. A resolucao de nomes sobe pela cadeia de pais, permitindo
sombreamento sem perder o simbolo do escopo externo. A primeira passada coleta
as assinaturas de todas as funcoes; a segunda verifica corpos, tipos e retornos.
"""
from dataclasses import dataclass, field

from mplc.erros import ErroMPL


TIPOS_RETORNO = {
    'TIPO_INTEIRO': 'inteiro',
    'TIPO_REAL': 'real',
    'TIPO_LOGICO': 'logico',
    'TIPO_TEXTO': 'texto',
    'TIPO_VAZIO': 'vazio',
}

TIPOS_VALOR = {'inteiro', 'real', 'logico', 'texto'}
NUMERICOS = {'inteiro', 'real'}


@dataclass
class Simbolo:
    nome: str
    categoria: str
    tipo: str
    linha: int
    parametros: tuple = ()
    escopo: int = 0


@dataclass
class Escopo:
    numero: int
    descricao: str
    pai: int | None
    simbolos: list = field(default_factory=list)

    def local(self, nome):
        for simbolo in self.simbolos:
            if simbolo.nome == nome:
                return simbolo
        return None


class AnalisadorSemantico:
    def __init__(self, arvore):
        self.arvore = arvore
        self.escopos = [Escopo(0, 'global', None)]
        self.atual = 0
        self.funcoes = {}
        self.funcao_atual = None

    def erro(self, no, mensagem, linha=None, coluna=None):
        linha = linha if linha is not None else getattr(no, 'linha', 1)
        coluna = coluna if coluna is not None else getattr(no, 'coluna', 1)
        raise ErroMPL('semantico', linha or 1, coluna or 1, mensagem)

    def abrir_escopo(self, descricao):
        numero = len(self.escopos)
        self.escopos.append(Escopo(numero, descricao, self.atual))
        self.atual = numero
        return numero

    def fechar_escopo(self):
        pai = self.escopos[self.atual].pai
        if pai is not None:
            self.atual = pai

    def simbolo_local(self, nome):
        return self.escopos[self.atual].local(nome)

    def buscar_variavel(self, nome):
        numero = self.atual
        while numero is not None:
            escopo = self.escopos[numero]
            simbolo = escopo.local(nome)
            if simbolo is not None and simbolo.categoria in ('parametro', 'variavel'):
                return simbolo
            numero = escopo.pai
        return None

    def adicionar_simbolo(self, simbolo, no, onde=None):
        escopo = self.escopos[self.atual]
        if escopo.local(simbolo.nome) is not None:
            self.erro(no, f"'{simbolo.nome}' ja declarado neste escopo")
        simbolo.escopo = escopo.numero
        escopo.simbolos.append(simbolo)

    def analisar(self):
        if getattr(self.arvore, 'rotulo', None) != 'programa':
            self.erro(self.arvore, 'raiz sintatica invalida')

        # Passada 1: todas as assinaturas ficam disponiveis antes dos corpos.
        funcoes = [n for n in self.arvore.filhos if n.rotulo.startswith('funcao ')]
        primeiro = funcoes[0] if funcoes else self.arvore
        for funcao in funcoes:
            nome = funcao.extra.get('nome')
            tipo = funcao.extra.get('tipo')
            parametros_no = funcao.filhos[0]
            tipos_param = tuple(p.extra.get('tipo') for p in parametros_no.filhos)
            if nome in self.funcoes:
                self.erro(funcao, f"funcao '{nome}' declarada mais de uma vez")
            simbolo = Simbolo(nome, 'funcao', tipo, funcao.linha, tipos_param, 0)
            self.funcoes[nome] = simbolo
            self.escopos[0].simbolos.append(simbolo)

        principal = self.funcoes.get('principal')
        if principal is None:
            self.erro(primeiro, "funcao 'principal' nao declarada")
        if principal.tipo != 'vazio' or principal.parametros:
            no_principal = next((f for f in funcoes if f.extra.get('nome') == 'principal'), primeiro)
            self.erro(no_principal, "'principal' deve retornar vazio e nao receber parametros")

        # Passada 2: cria os escopos em ordem de abertura e verifica os corpos.
        for funcao in funcoes:
            self._analisar_funcao(funcao)

        return self.escopos

    def _analisar_funcao(self, no):
        nome = no.extra['nome']
        tipo_retorno = no.extra['tipo']
        self.funcao_atual = {'nome': nome, 'tipo': tipo_retorno, 'no': no}

        parametros_no, bloco_no = no.filhos
        self.abrir_escopo(f'funcao {nome}')
        try:
            for parametro in parametros_no.filhos:
                nome_param = parametro.extra['nome']
                tipo_param = parametro.extra['tipo']
                simbolo = Simbolo(nome_param, 'parametro', tipo_param, parametro.linha)
                self.adicionar_simbolo(simbolo, parametro)
            garante = self._analisar_bloco(bloco_no)
            if tipo_retorno != 'vazio' and not garante:
                self.erro(no, f"a funcao '{nome}' pode terminar sem retorne")
        finally:
            self.fechar_escopo()
            self.funcao_atual = None

    def _analisar_bloco(self, no):
        self.abrir_escopo('bloco')
        garante_retorno = False
        try:
            for comando in no.filhos:
                comando_retorna = self._analisar_comando(comando)
                # Uma sequencia garante retorno se algum comando executado
                # incondicionalmente garante retorno. Um se sem senao nao faz isso.
                if comando_retorna:
                    garante_retorno = True
        finally:
            self.fechar_escopo()
        return garante_retorno

    def _analisar_comando(self, no):
        rotulo = no.rotulo
        if rotulo == 'bloco':
            return self._analisar_bloco(no)

        if rotulo.startswith('declaracao '):
            nome = no.extra['nome']
            tipo = no.extra['tipo']
            if self.simbolo_local(nome) is not None:
                self.erro(no, f"'{nome}' ja declarado neste escopo")
            if no.filhos:
                tipo_expr = self._tipo_expressao(no.filhos[0])
                if not self._atribuivel(tipo, tipo_expr):
                    self.erro(no, f"nao e possivel inicializar '{nome}' ({tipo}) com {tipo_expr}")
                self._marcar_conversao(no.filhos[0], tipo, tipo_expr)
            simbolo = Simbolo(nome, 'variavel', tipo, no.linha)
            self.escopos[self.atual].simbolos.append(simbolo)
            simbolo.escopo = self.atual
            return False

        if rotulo.startswith('atribuicao '):
            nome = no.extra['nome']
            simbolo = self.buscar_variavel(nome)
            if simbolo is None:
                self.erro(no, f"variavel '{nome}' nao declarada")
            tipo_expr = self._tipo_expressao(no.filhos[0])
            if not self._atribuivel(simbolo.tipo, tipo_expr):
                self.erro(no, f"nao e possivel atribuir {tipo_expr} a '{nome}' ({simbolo.tipo})")
            self._marcar_conversao(no.filhos[0], simbolo.tipo, tipo_expr)
            no.extra['tipo_destino'] = simbolo.tipo
            return False

        if rotulo == 'se':
            tipo_condicao = self._tipo_expressao(no.filhos[0])
            if tipo_condicao != 'logico':
                self.erro(no.filhos[0], "a condicao de 'se' deve ser logica")
            retorna_entao = self._analisar_bloco(no.filhos[1])
            if len(no.filhos) == 3:
                retorna_senao = self._analisar_bloco(no.filhos[2])
                return retorna_entao and retorna_senao
            return False

        if rotulo == 'enquanto':
            tipo_condicao = self._tipo_expressao(no.filhos[0])
            if tipo_condicao != 'logico':
                self.erro(no.filhos[0], "a condicao de 'enquanto' deve ser logica")
            self._analisar_bloco(no.filhos[1])
            return False

        if rotulo == 'escreva':
            tipo_expr = self._tipo_expressao(no.filhos[0])
            if tipo_expr == 'vazio':
                self.erro(no.filhos[0], "escreva nao aceita uma expressao vazio")
            return False

        if rotulo == 'retorne':
            tipo_retorno = self.funcao_atual['tipo']
            if tipo_retorno == 'vazio':
                if no.filhos:
                    self.erro(no, "funcao vazio nao pode retornar um valor")
                return True
            if not no.filhos:
                self.erro(no, f"funcao {tipo_retorno} precisa retornar um valor")
            tipo_expr = self._tipo_expressao(no.filhos[0])
            if not self._atribuivel(tipo_retorno, tipo_expr):
                self.erro(no, f"retorno {tipo_expr} incompatível com {tipo_retorno}")
            self._marcar_conversao(no.filhos[0], tipo_retorno, tipo_expr)
            no.extra['tipo_retorno'] = tipo_retorno
            return True

        if rotulo.startswith('chamada '):
            self._tipo_chamada(no, como_expressao=False)
            return False

        self.erro(no, f"comando semantico desconhecido: {rotulo}")

    @staticmethod
    def _atribuivel(destino, origem):
        return destino == origem or (destino == 'real' and origem == 'inteiro')

    @staticmethod
    def _marcar_conversao(no, destino, origem):
        # Anotacao reutilizavel pela futura geracao de codigo da Entrega 4.
        if destino == 'real' and origem == 'inteiro':
            no.extra['converter_para'] = 'real'

    def _tipo_expressao(self, no):
        rotulo = no.rotulo
        if rotulo.startswith('literal '):
            tipo = no.extra.get('tipo') or rotulo.split(' ', 2)[1]
            no.extra['tipo_semantico'] = tipo
            return tipo

        if rotulo.startswith('variavel '):
            nome = no.extra.get('nome', rotulo[len('variavel '):])
            simbolo = self.buscar_variavel(nome)
            if simbolo is None:
                self.erro(no, f"variavel '{nome}' nao declarada")
            no.extra['tipo_semantico'] = simbolo.tipo
            no.extra['simbolo'] = simbolo
            return simbolo.tipo

        if rotulo.startswith('chamada '):
            return self._tipo_chamada(no, como_expressao=True)

        if rotulo.startswith('unario '):
            op = no.extra.get('operador', rotulo[len('unario '):])
            tipo = self._tipo_expressao(no.filhos[0])
            if op == 'nao':
                if tipo != 'logico':
                    self.erro(no, "o operador 'nao' exige logico")
                resultado = 'logico'
            else:
                if tipo not in NUMERICOS:
                    self.erro(no, "o menos unario exige operando numerico")
                resultado = tipo
            no.extra['tipo_semantico'] = resultado
            return resultado

        if rotulo.startswith('binario '):
            op = no.extra.get('operador', rotulo[len('binario '):])
            tipo_esq = self._tipo_expressao(no.filhos[0])
            tipo_dir = self._tipo_expressao(no.filhos[1])
            resultado = self._tipo_binario(no, op, tipo_esq, tipo_dir)
            no.extra['tipo_semantico'] = resultado
            return resultado

        self.erro(no, f"expressao semantica desconhecida: {rotulo}")

    def _tipo_binario(self, no, op, a, b):
        if op in ('+', '-', '*', '/'):
            if op == '+' and a == b == 'texto':
                return 'texto'
            if a in NUMERICOS and b in NUMERICOS:
                if 'real' in (a, b):
                    for filho, tipo in zip(no.filhos, (a, b)):
                        self._marcar_conversao(filho, 'real', tipo)
                    return 'real'
                return 'inteiro'
            self.erro(no, f"operador '{op}' exige operandos numericos compatíveis")

        if op == '%':
            if a == b == 'inteiro':
                return 'inteiro'
            self.erro(no, "o operador '%' exige dois operandos inteiros")

        if op in ('==', '!='):
            if a == b or (a in NUMERICOS and b in NUMERICOS):
                if a in NUMERICOS and b in NUMERICOS and a != b:
                    for filho, tipo in zip(no.filhos, (a, b)):
                        self._marcar_conversao(filho, 'real', tipo)
                return 'logico'
            self.erro(no, f"operandos de '{op}' possuem tipos incompatíveis")

        if op in ('<', '<=', '>', '>='):
            if a in NUMERICOS and b in NUMERICOS:
                if a != b:
                    for filho, tipo in zip(no.filhos, (a, b)):
                        self._marcar_conversao(filho, 'real', tipo)
                return 'logico'
            self.erro(no, f"o operador '{op}' exige operandos numericos")

        if op in ('e', 'ou'):
            if a == b == 'logico':
                return 'logico'
            self.erro(no, f"o operador '{op}' exige dois operandos logicos")

        self.erro(no, f"operador desconhecido: {op}")

    def _tipo_chamada(self, no, como_expressao):
        nome = no.extra.get('nome') or no.rotulo[len('chamada '):]
        funcao = self.funcoes.get(nome)
        if funcao is None:
            self.erro(no, f"funcao '{nome}' nao declarada")

        argumentos = no.filhos
        if len(argumentos) != len(funcao.parametros):
            self.erro(no, f"funcao '{nome}' espera {len(funcao.parametros)} argumento(s), recebeu {len(argumentos)}")

        for i, (argumento, tipo_param) in enumerate(zip(argumentos, funcao.parametros)):
            tipo_arg = self._tipo_expressao(argumento)
            if not self._atribuivel(tipo_param, tipo_arg):
                self.erro(argumento, f"argumento {i + 1} de '{nome}' espera {tipo_param}, recebeu {tipo_arg}")
            self._marcar_conversao(argumento, tipo_param, tipo_arg)

        if como_expressao and funcao.tipo == 'vazio':
            self.erro(no, f"funcao vazio '{nome}' nao pode ser usada em expressao")
        no.extra['tipo_semantico'] = funcao.tipo
        no.extra['simbolo'] = funcao
        return funcao.tipo

    def despejar(self):
        linhas = []
        for escopo in self.escopos:
            if escopo.numero == 0:
                linhas.append('escopo 0 global')
            else:
                linhas.append(f'escopo {escopo.numero} {escopo.descricao} pai {escopo.pai}')
            for simbolo in escopo.simbolos:
                if simbolo.categoria == 'funcao':
                    assinatura = ','.join(simbolo.parametros)
                    linhas.append(
                        f'  {simbolo.nome}|funcao|{simbolo.tipo}({assinatura})|{simbolo.linha}'
                    )
                else:
                    linhas.append(
                        f'  {simbolo.nome}|{simbolo.categoria}|{simbolo.tipo}|{simbolo.linha}'
                    )
        return linhas


def analisar(arvore):
    """Monta a tabela de simbolos e verifica os tipos do programa."""
    return AnalisadorSemantico(arvore).analisar()


def despejar(tabela):
    """Devolve as linhas do --tabela, no formato da secao 4 do contrato."""
    linhas = []
    for escopo in tabela:
        if escopo.numero == 0:
            linhas.append('escopo 0 global')
        else:
            linhas.append(f'escopo {escopo.numero} {escopo.descricao} pai {escopo.pai}')
        for simbolo in escopo.simbolos:
            if simbolo.categoria == 'funcao':
                assinatura = ','.join(simbolo.parametros)
                linhas.append(f'  {simbolo.nome}|funcao|{simbolo.tipo}({assinatura})|{simbolo.linha}')
            else:
                linhas.append(f'  {simbolo.nome}|{simbolo.categoria}|{simbolo.tipo}|{simbolo.linha}')
    return linhas
