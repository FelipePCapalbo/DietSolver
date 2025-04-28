# Otimizador de Cardápios com Ajuste de Macros

Este programa interativo em Python propõe cardápios personalizados **minimizando os desvios** em relação às metas diárias de macronutrientes  
(proteína, carboidrato e gordura) e **respeitando** a restrição calórica total e os limites de porção de cada alimento.

---

## Funcionalidades

- Leitura das metas de macros em `Macros.json`
- Seleção manual de alimentos disponíveis a partir de `Alimentos.json`
- **Programação Linear Inteira** para otimizar as quantidades
- Geração de até **5 cardápios** distintos com desvios mínimos
- Limites opcionais de consumo mínimo/máximo por alimento

---

## Formato dos Arquivos

### `Macros.json`

```json
{
  "Proteina": 130,
  "Carboidrato": 250,
  "Gordura": 60
}
```

### `Alimentos.json`

| Campo        | Descrição                                                            |
|--------------|-----------------------------------------------------------------------|
| `Nome`       | Nome do alimento                                                     |
| `Porcao`     | Quantidade base (g ou unid.) para os macros informados               |
| `Proteina`   | g de proteína por porção                                             |
| `Carboidrato`| g de carboidrato por porção                                          |
| `Gordura`    | g de gordura por porção                                              |
| `Unidade`    | `"Gramas"` *(default)* ou `"Unidades"`                               |
| `Min`        | (opcional) consumo mínimo permitido                                  |
| `Max`        | (opcional) consumo máximo permitido                                  |

---

## Modelagem Matemática

### Variáveis

| Símbolo | Significado                                   |
|---------|-----------------------------------------------|
| \(y_i\) | quantidade do alimento *i* em **blocos** (inteiro) |
| \(m_i\) | multiplicador do bloco (*10 g* se `Gramas`, *1* se `Unidades`) |
| \(P_i, C_i, F_i\) | macros por porção (g) de proteína, carboidrato e gordura |
| \(p^\*, c^\*, f^\*\) | metas diárias de proteína, carboidrato e gordura |
| \(\delta_p,\; \delta_c,\; \delta_f\) | desvios absolutos (variáveis contínuas) |

### Expressões dos macros entregues

\[
\begin{aligned}
P &= \sum_{i} m_i\,y_i \\frac{P_i}{\text{Porção}_i} \\\
C &= \sum_{i} m_i\,y_i \\frac{C_i}{\text{Porção}_i} \\\
F &= \sum_{i} m_i\,y_i \\frac{F_i}{\text{Porção}_i}
\end{aligned}
\]

### Restrição calórica

\[
\sum_{i} m_i\,y_i\,
\frac{4P_i + 4C_i + 9F_i}{\text{Porção}_i}
\;=\;
\underbrace{4p^\* + 4c^\* + 9f^\*}_{\text{caloria-meta}}
\]

### Linearização dos desvios absolutos

\[
\begin{cases}
P - p^\* \;\le\; \delta_p \\
 p^\* - P \;\le\; \delta_p
\end{cases}
\quad
\begin{cases}
C - c^\* \;\le\; \delta_c \\
 c^\* - C \;\le\; \delta_c
\end{cases}
\quad
\begin{cases}
F - f^\* \;\le\; \delta_f \\
 f^\* - F \;\le\; \delta_f
\end{cases}
\]

### Função-objetivo

Minimizar o desvio relativo total:

\[
\min\;
\left(\frac{\delta_p}{p^\*}\right) +
\left(\frac{\delta_c}{c^\*}\right) +
\left(\frac{\delta_f}{f^\*}\right)
\]

### Outras restrições

- **Limites de porção:**  \(\text{Min}_i \le m_i\,y_i \le \text{Max}_i\)
- **Variáveis inteiras:** \(y_i \in \mathbb{Z}_{\ge 0}\)

Após cada solução ótima, adiciona-se um “No-Good Cut” para garantir que o próximo cardápio difira em pelo menos um alimento, permitindo gerar até 5 soluções.

---

## Requisitos

- Python 3.7+
- Biblioteca **`pulp`**

```bash
pip install pulp
```

---

## Execução

```bash
python solver.py
```

Escolha os alimentos no menu interativo e receba os cardápios otimizados.

---

## Exemplo de Saída

```text
--- Cardápio 1 ---
Frango: 200 Gramas
Arroz: 150 Gramas
Abacate: 50 Gramas
Calorias Totais: 2200.0 cal
Macros entregues:
  Proteína: 130.0g (meta: 130g)
  Carboidrato: 250.0g (meta: 250g)
  Gordura:  60.0g (meta: 60g)
Valor do Objetivo (desvios normalizados): 0.0000
```

---
