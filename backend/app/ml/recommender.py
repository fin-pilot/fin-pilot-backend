class FinanceRecommender:
    def __init__(self):
        self.rules = {"Needs": 0.50, "Wants": 0.30, "Savings": 0.20}

    def analyze_spending(
        self, income: float, expenses_by_category: dict
    ) -> list:
        recommendations = []
        total_expenses = sum(expenses_by_category.values())

        if total_expenses > income * 0.9:
            recommendations.append(
                "Критичний рівень витрат: Ви витратили понад 90% свого доходу."
            )

        if "Savings" in expenses_by_category:
            if expenses_by_category["Savings"] < income * self.rules["Savings"]:
                recommendations.append(
                    "Рекомендація: Спробуйте збільшити частку заощаджень до 20% від доходу."
                )
        else:
            recommendations.append(
                "Рекомендація: У вас відсутні транзакції в категорії 'Заощадження'."
            )

        wants_spending = expenses_by_category.get(
            "Entertainment", 0
        ) + expenses_by_category.get("Restaurants", 0)
        if wants_spending > income * self.rules["Wants"]:
            recommendations.append(
                "Оптимізація: Витрати на розваги перевищують 30%."
            )

        return recommendations
