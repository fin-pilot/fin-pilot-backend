from typing import Dict, List
from backend.app.schemas.analytics import RecommendationItem


class FinanceRecommender:
    def analyze_spending(
        self, income: float, expenses_by_category: Dict[str, float]
    ) -> List[RecommendationItem]:
        recommendations = []
        total_expense = sum(expenses_by_category.values())

        if income > 0:
            savings_rate = (income - total_expense) / income
            if savings_rate < 0:
                recommendations.append(
                    RecommendationItem(
                        text="Увага: Ваші витрати перевищують доходи! Перегляньте свої необов'язкові витрати.",
                        type="error",
                        action_link="/transactions",
                    )
                )
            elif savings_rate < 0.1:
                recommendations.append(
                    RecommendationItem(
                        text="Ваш рівень заощаджень становить менше 10%. Бажано оптимізувати бюджет.",
                        type="warning",
                        action_link="/budgets",
                    )
                )
            elif savings_rate > 0.3:
                recommendations.append(
                    RecommendationItem(
                        text="Чудова робота! Ви відкладаєте понад 30% свого доходу.",
                        type="success",
                        action_link="/goals",
                    )
                )

        if total_expense > 0:
            highest_cat = max(
                expenses_by_category, key=expenses_by_category.get
            )
            highest_amt = expenses_by_category[highest_cat]
            if (highest_amt / total_expense) > 0.4:
                recommendations.append(
                    RecommendationItem(
                        text=f"Понад 40% ваших витрат припадає на '{highest_cat}'. Перевірте цю категорію.",
                        type="warning",
                        action_link="/analytics",
                    )
                )

        if not recommendations:
            recommendations.append(
                RecommendationItem(
                    text="Ваші фінанси збалансовані. Продовжуйте дотримуватись свого плану!",
                    type="info",
                    action_link="/",
                )
            )

        return recommendations
