import os
import json
from pulp import LpProblem, LpVariable, LpInteger, LpContinuous, lpSum, LpStatus, value

# Função que retorna o multiplicador de quantidade, de acordo com a unidade do alimento
def get_multiplier(alimento):
    # Se a unidade for "Unidades", o bloco representa 1 unidade; se for "Gramas", o bloco representa 10g.
    if alimento.get("Unidade", "Gramas") == "Unidades":
        return 1
    else:
        return 10

# Função para calcular a contribuição de um alimento para um macronutriente
def macro_contrib(alimento, macro, y, multiplier):
    # A contribuição é dada pelo valor do macronutriente (por porção) escalado pela quantidade efetiva (y * multiplier)
    return multiplier * y * (alimento[macro] / alimento["Porcao"])

# Função para calcular a contribuição calórica de um alimento
def calorias_contrib(alimento, y, multiplier):
    # Calcula as calorias por porção e multiplica pela quantidade efetiva
    cal_por_porcao = (alimento["Proteina"] * 4 +
                      alimento["Carboidrato"] * 4 +
                      alimento["Gordura"] * 9) / alimento["Porcao"]
    return multiplier * y * cal_por_porcao

# === Definindo os caminhos para os arquivos JSON (localizados no mesmo diretório do script) ===
script_dir = os.path.dirname(os.path.abspath(__file__))
macros_path = os.path.join(script_dir, "Macros.json")
alimentos_path = os.path.join(script_dir, "Alimentos.json")

# === 1. Leitura dos arquivos JSON ===
with open(macros_path, "r", encoding="utf-8") as f:
    macros_data = json.load(f)

target_protein = macros_data["Proteina"]
target_fat     = macros_data["Gordura"]
target_carb    = macros_data["Carboidrato"]
target_calories = target_protein * 4 + target_carb * 4 + target_fat * 9

with open(alimentos_path, "r", encoding="utf-8") as f:
    alimentos = json.load(f)

# === 2. Seleção dinâmica dos alimentos ===
selected_alimentos = []
available_alimentos = alimentos.copy()

print("Selecione os alimentos para compor o cardápio:")

while True:
    print("\nOpções disponíveis:")
    for idx, alimento in enumerate(available_alimentos, start=1):
        # Exibe nome e unidade
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

# Cria um dicionário com os multiplicadores para cada alimento
multipliers = {}
for alimento in selected_alimentos:
    nome = alimento["Nome"]
    multipliers[nome] = get_multiplier(alimento)

# === 5. Otimização por Minimização dos Erros dos Macros ===
# Nesta modelagem, o objetivo é minimizar a soma ponderada dos desvios absolutos entre os macros entregues e as metas.
min_error_model = LpProblem("Cardapio_MinErro", sense=1)  # sense=1 equivale a LpMinimize

# Variáveis de decisão: para cada alimento, a quantidade (em blocos) com lower bound 1
y_vars_error = {}
for alimento in selected_alimentos:
    nome = alimento["Nome"]
    y_vars_error[nome] = LpVariable(f"y_err_{nome}", lowBound=1, cat=LpInteger)

# Expressões para os macros entregues pelo cardápio
protein_expr = lpSum(macro_contrib(alimento, "Proteina", y_vars_error[alimento["Nome"]], multipliers[alimento["Nome"]])
                     for alimento in selected_alimentos)
carb_expr = lpSum(macro_contrib(alimento, "Carboidrato", y_vars_error[alimento["Nome"]], multipliers[alimento["Nome"]])
                  for alimento in selected_alimentos)
fat_expr = lpSum(macro_contrib(alimento, "Gordura", y_vars_error[alimento["Nome"]], multipliers[alimento["Nome"]])
                 for alimento in selected_alimentos)

# Variáveis de desvio (delta): representam a diferença absoluta entre o macro entregue e a meta
delta_prot = LpVariable("delta_prot", lowBound=0, cat=LpContinuous)
delta_carb = LpVariable("delta_carb", lowBound=0, cat=LpContinuous)
delta_fat  = LpVariable("delta_fat", lowBound=0, cat=LpContinuous)

# Restrições para linearizar o valor absoluto:
# Para proteína:
min_error_model += protein_expr - target_protein <= delta_prot, "DeltaProt_1"
min_error_model += target_protein - protein_expr <= delta_prot, "DeltaProt_2"
# Para carboidrato:
min_error_model += carb_expr - target_carb <= delta_carb, "DeltaCarb_1"
min_error_model += target_carb - carb_expr <= delta_carb, "DeltaCarb_2"
# Para gordura:
min_error_model += fat_expr - target_fat <= delta_fat, "DeltaFat_1"
min_error_model += target_fat - fat_expr <= delta_fat, "DeltaFat_2"

# (Opcional) Restrição para que o total de calorias seja exatamente o desejado
calories_expr = lpSum(calorias_contrib(alimento, y_vars_error[alimento["Nome"]], multipliers[alimento["Nome"]])
                      for alimento in selected_alimentos)
min_error_model += calories_expr == target_calories, "Restricao_Calorias"

# Definindo os pesos normalizadores para cada macro (usando os inversos das metas)
w_prot = 1 / target_protein
w_carb = 1 / target_carb
w_fat  = 1 / target_fat

# Função objetivo: minimizar a soma ponderada dos desvios
min_error_model += w_prot * delta_prot + w_carb * delta_carb + w_fat * delta_fat, "Objetivo_Min_Erro"

min_error_status = min_error_model.solve()

print("\n=== Resultado da otimização por minimização dos erros dos macros ===")
if LpStatus[min_error_model.status] == "Optimal":
    total_calorias = 0
    total_prot = 0
    total_carb = 0
    total_fat = 0
    for alimento in selected_alimentos:
        nome = alimento["Nome"]
        y_val = value(y_vars_error[nome])
        qtd = multipliers[nome] * y_val
        cal_alimento = calorias_contrib(alimento, y_val, multipliers[nome])
        prot_alimento = macro_contrib(alimento, "Proteina", y_val, multipliers[nome])
        carb_alimento = macro_contrib(alimento, "Carboidrato", y_val, multipliers[nome])
        fat_alimento = macro_contrib(alimento, "Gordura", y_val, multipliers[nome])
        
        total_calorias += cal_alimento
        total_prot += prot_alimento
        total_carb += carb_alimento
        total_fat += fat_alimento
        
        print(f"{nome}: {int(qtd)} {alimento.get('Unidade', 'Gramas')} - Calorias: {cal_alimento:.1f}")
    
    print(f"\nTotal de calorias: {total_calorias:.1f} cal")
    print("Macros entregues:")
    print(f"  Proteína: {total_prot:.1f}g (meta: {target_protein}g)")
    print(f"  Carboidrato: {total_carb:.1f}g (meta: {target_carb}g)")
    print(f"  Gordura: {total_fat:.1f}g (meta: {target_fat}g)")
    
    # Também podemos exibir os desvios normalizados:
    dev_prot = value(delta_prot)
    dev_carb = value(delta_carb)
    dev_fat  = value(delta_fat)
    print("\nDesvios absolutos (normalizados):")
    print(f"  Proteína: {w_prot * dev_prot:.4f}")
    print(f"  Carboidrato: {w_carb * dev_carb:.4f}")
    print(f"  Gordura: {w_fat * dev_fat:.4f}")
else:
    print("Não foi possível encontrar uma solução que minimize o erro dos macros.")
