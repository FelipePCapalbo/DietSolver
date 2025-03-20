import os
import json
import math
from pulp import (
    LpProblem, LpVariable, LpInteger, LpContinuous, lpSum,
    LpStatus, value, LpMinimize
)

# --- Funções utilitárias ---

def get_multiplier(alimento):
    """
    Retorna o multiplicador: para 'Gramas' é 10 (bloco = 10g);
    para 'Unidades' é 1 (bloco = 1 unidade).
    """
    if alimento.get("Unidade", "Gramas") == "Unidades":
        return 1
    else:
        return 10

def macro_contrib(alimento, macro, y, multiplier):
    """
    Contribuição para o macro (em gramas):
      (valor do macro na porção / Porcao) * (quantidade efetiva = y * multiplier)
    """
    return multiplier * y * (alimento[macro] / alimento["Porcao"])

def calorias_contrib(alimento, y, multiplier):
    """
    Contribuição calórica do alimento, usando:
      4 cal/g para Proteína e Carboidrato e 9 cal/g para Gordura.
    """
    cal_por_porcao = ((alimento["Proteina"] * 4 +
                       alimento["Carboidrato"] * 4 +
                       alimento["Gordura"] * 9) / alimento["Porcao"])
    return multiplier * y * cal_por_porcao

# --- Definindo os caminhos para os arquivos JSON ---
script_dir = os.path.dirname(os.path.abspath(__file__))
macros_path = os.path.join(script_dir, "Macros.json")
alimentos_path = os.path.join(script_dir, "Alimentos.json")

# --- 1. Leitura dos arquivos JSON ---
with open(macros_path, "r", encoding="utf-8") as f:
    macros_data = json.load(f)

target_protein = macros_data["Proteina"]
target_fat     = macros_data["Gordura"]
target_carb    = macros_data["Carboidrato"]
target_calories = target_protein * 4 + target_carb * 4 + target_fat * 9

with open(alimentos_path, "r", encoding="utf-8") as f:
    alimentos = json.load(f)

# --- 2. Seleção dinâmica dos alimentos ---
selected_alimentos = []
available_alimentos = alimentos.copy()

print("Selecione os alimentos para compor o cardápio:")
while True:
    print("\nOpções disponíveis:")
    for idx, alimento in enumerate(available_alimentos, start=1):
        print(f"{idx}. {alimento['Nome']} ({alimento.get('Unidade', 'Gramas')})")
    print("0. Parar a seleção")
    
    try:
        escolha = int(input("Digite o número do alimento desejado (ou 0 para parar): "))
    except ValueError:
        print("Por favor, digite um número válido.")
        continue

    if escolha == 0:
        break
    elif 1 <= escolha <= len(available_alimentos):
        selected = available_alimentos.pop(escolha - 1)
        selected_alimentos.append(selected)
        print(f"Você selecionou: {selected['Nome']} ({selected.get('Unidade', 'Gramas')})")
    else:
        print("Opção inválida. Tente novamente.")

if not selected_alimentos:
    print("Nenhum alimento foi selecionado. O programa será encerrado.")
    exit()

# --- 3. Definição dos limites para as variáveis de decisão ---
# Cada variável representa a quantidade (em blocos) de cada alimento.
# Se "Min" for 0 (ou ausente) usa-se o default: 10g para alimentos em Gramas (ou 1 para Unidades).
bounds = {}
for alimento in selected_alimentos:
    nome = alimento["Nome"]
    multiplier = get_multiplier(alimento)
    if alimento.get("Min", 0) > 0:
        lb = math.ceil(alimento["Min"] / multiplier)
    else:
        lb = 1
    if alimento.get("Max", 0) > 0:
        ub = math.floor(alimento["Max"] / multiplier)
    else:
        ub = None
    bounds[nome] = (lb, ub)

# --- 4. Modelagem do problema: Minimização dos desvios dos macros com pesos normalizadores ---
min_error_model = LpProblem("Cardapio_MinErro", LpMinimize)

# Variáveis de decisão: para cada alimento, y_vars_error com limites conforme bounds
y_vars_error = {}
for alimento in selected_alimentos:
    nome = alimento["Nome"]
    lb, ub = bounds[nome]
    y_vars_error[nome] = LpVariable(f"y_err_{nome}", lowBound=lb, upBound=ub, cat=LpInteger)

# Expressões dos macros entregues
protein_expr = lpSum(macro_contrib(alimento, "Proteina", y_vars_error[alimento["Nome"]], get_multiplier(alimento))
                     for alimento in selected_alimentos)
carb_expr = lpSum(macro_contrib(alimento, "Carboidrato", y_vars_error[alimento["Nome"]], get_multiplier(alimento))
                  for alimento in selected_alimentos)
fat_expr = lpSum(macro_contrib(alimento, "Gordura", y_vars_error[alimento["Nome"]], get_multiplier(alimento))
                 for alimento in selected_alimentos)

# Variáveis para os desvios absolutos
delta_prot = LpVariable("delta_prot", lowBound=0, cat=LpContinuous)
delta_carb = LpVariable("delta_carb", lowBound=0, cat=LpContinuous)
delta_fat  = LpVariable("delta_fat", lowBound=0, cat=LpContinuous)

# Linearização dos desvios (valor absoluto)
min_error_model += protein_expr - target_protein <= delta_prot, "DeltaProt_1"
min_error_model += target_protein - protein_expr <= delta_prot, "DeltaProt_2"
min_error_model += carb_expr - target_carb <= delta_carb, "DeltaCarb_1"
min_error_model += target_carb - carb_expr <= delta_carb, "DeltaCarb_2"
min_error_model += fat_expr - target_fat <= delta_fat, "DeltaFat_1"
min_error_model += target_fat - fat_expr <= delta_fat, "DeltaFat_2"

# Restrição opcional para manter as calorias consistentes
calories_expr = lpSum(calorias_contrib(alimento, y_vars_error[alimento["Nome"]], get_multiplier(alimento))
                      for alimento in selected_alimentos)
min_error_model += calories_expr == target_calories, "Restricao_Calorias"

# Pesos normalizadores (inversos das metas)
w_prot = 1 / target_protein
w_carb = 1 / target_carb
w_fat  = 1 / target_fat

# Função objetivo: minimizar a soma ponderada dos desvios
min_error_model += w_prot * delta_prot + w_carb * delta_carb + w_fat * delta_fat, "Objetivo_Min_Erro"

# --- 5. Geração dos cardápios distintos ---
# Neste laço, após cada solução encontrada, adicionamos cortes "no-good"
# que forçam que a próxima solução difira da atual em pelo menos um alimento.
solutions = []             # Armazena (solução, valor_obj, prot_total, carb_total, fat_total, cal_total)
solution_signatures = set()  # Para evitar duplicatas

k = 0
max_solucoes = 5
while k < max_solucoes:
    status = min_error_model.solve()
    if LpStatus[min_error_model.status] != "Optimal":
        break

    # Extrai a solução corrente
    sol = {alimento["Nome"]: value(y_vars_error[alimento["Nome"]]) for alimento in selected_alimentos}
    sol_signature = tuple(sorted((nome, sol[nome]) for nome in sol))
    
    # Se esta solução já foi gerada, encerra o loop
    if sol_signature in solution_signatures:
        break
    solution_signatures.add(sol_signature)
    obj_val = value(min_error_model.objective)
    
    # Calcula os macros e as calorias totais
    tot_prot = sum(macro_contrib(alimento, "Proteina", sol[alimento["Nome"]], get_multiplier(alimento))
                   for alimento in selected_alimentos)
    tot_carb = sum(macro_contrib(alimento, "Carboidrato", sol[alimento["Nome"]], get_multiplier(alimento))
                   for alimento in selected_alimentos)
    tot_fat = sum(macro_contrib(alimento, "Gordura", sol[alimento["Nome"]], get_multiplier(alimento))
                  for alimento in selected_alimentos)
    tot_cal = sum(calorias_contrib(alimento, sol[alimento["Nome"]], get_multiplier(alimento))
                  for alimento in selected_alimentos)
    
    solutions.append((sol, obj_val, tot_prot, tot_carb, tot_fat, tot_cal))
    
    # Adiciona cortes "no-good" usando variáveis binárias para cada alimento.
    # Para cada alimento, definimos uma variável binária d que forçará que:
    #    y - sol_value <= M * d   e   sol_value - y <= M * d.
    # Então, somamos os d e forçamos que a soma seja pelo menos 1.
    d_vars = {}
    for alimento in selected_alimentos:
        nome = alimento["Nome"]
        lb, ub = bounds[nome]
        # Define M_i como a amplitude do domínio (ou um número grande se não houver limite superior)
        M_i = (ub - lb) if ub is not None else 1000
        d_vars[nome] = LpVariable(f"d_{nome}_{k}", cat="Binary")
        min_error_model += y_vars_error[nome] - sol[nome] <= M_i * d_vars[nome], f"NGC_{nome}_1_{k}"
        min_error_model += sol[nome] - y_vars_error[nome] <= M_i * d_vars[nome], f"NGC_{nome}_2_{k}"
    min_error_model += lpSum(d_vars[nome] for nome in d_vars) >= 1, f"NoGoodCut_{k}"
    
    k += 1

# --- 6. Apresentação dos cardápios encontrados ---
if solutions:
    # Ordena as soluções pelo valor do objetivo (quanto menor, melhor)
    solutions.sort(key=lambda s: s[1])
    print("\n=== Top Cardápios Propostos ===")
    for idx, sol_data in enumerate(solutions, start=1):
        sol, obj_val, tot_prot, tot_carb, tot_fat, tot_cal = sol_data
        print(f"\n--- Cardápio {idx} ---")
        for alimento in selected_alimentos:
            nome = alimento["Nome"]
            qtd = get_multiplier(alimento) * sol[nome]
            print(f"{nome}: {int(qtd)} {alimento.get('Unidade', 'Gramas')}")
        print(f"Calorias Totais: {tot_cal:.1f} cal")
        print("Macros entregues:")
        print(f"  Proteína: {tot_prot:.1f}g (meta: {target_protein}g)")
        print(f"  Carboidrato: {tot_carb:.1f}g (meta: {target_carb}g)")
        print(f"  Gordura: {tot_fat:.1f}g (meta: {target_fat}g)")
        print(f"Valor do Objetivo (desvios normalizados): {obj_val:.4f}")
else:
    print("Não foi possível encontrar nenhuma solução factível distinta.")
