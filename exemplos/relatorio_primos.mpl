// Relatorio de numeros primos: demonstra funcoes, repeticao, condicoes e logica.
funcao logico ehPrimo(inteiro n) {
  se (n < 2) {
    retorne falso;
  }
  inteiro divisor = 2;
  enquanto (divisor * divisor <= n) {
    se (n % divisor == 0) {
      retorne falso;
    }
    divisor = divisor + 1;
  }
  retorne verdadeiro;
}

funcao vazio principal() {
  inteiro numero = 1;
  inteiro quantidade = 0;
  escreva("Relatorio de numeros primos ate 30");
  enquanto (numero <= 30) {
    se (ehPrimo(numero)) {
      escreva(numero);
      quantidade = quantidade + 1;
    }
    numero = numero + 1;
  }
  escreva("Total de primos:");
  escreva(quantidade);
}
