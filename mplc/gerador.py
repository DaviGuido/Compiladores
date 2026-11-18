"""Tradutor do IR para instrucoes de uma VM de pilha, em JSONL legivel."""
import json


def gerar(codigo_intermediario):
    bytecode = []
    for i in codigo_intermediario.instrucoes:
        op = i['op']; linha = i.get('linha', 1)
        def add(opcode, **campos):
            bytecode.append(dict(op=opcode, linha=linha, **campos))
        if op == 'FUNC': add('FUNC', nome=i['nome'], tipo=i['tipo'], parametros=i['parametros'])
        elif op == 'END': add('END', nome=i['nome'])
        elif op == 'CONST': add('PUSH', valor=i['valor'], tipo=i['tipo'])
        elif op == 'DEFAULT': add('DEFAULT', slot=i['slot'], tipo=i['tipo'])
        elif op == 'LOAD': add('LOAD', slot=i['slot'])
        elif op == 'STORE': add('STORE', slot=i['slot'])
        elif op == 'CAST': add('CAST_REAL')
        elif op == 'UN': add('UNARY', operador=i['operador'])
        elif op == 'BIN': add('BINARY', operador=i['operador'])
        elif op == 'PRINT': add('PRINT')
        elif op == 'JZ': add('JZ', destino=i['destino'])
        elif op == 'JMP': add('JMP', destino=i['destino'])
        elif op == 'LABEL': add('LABEL', nome=i['nome'])
        elif op == 'CALL': add('CALL', funcao=i['funcao'], quantidade=len(i['argumentos']), tipo=i.get('tipo', 'vazio'))
        elif op == 'RET': add('RET', tem_valor=i.get('origem') is not None)
        else: raise ValueError(f'instrucao IR desconhecida: {op}')
    return [json.dumps(i, ensure_ascii=False, separators=(',', ':')) for i in bytecode]
