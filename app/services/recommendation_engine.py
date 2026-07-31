from app.services.marketing_intelligence import MarketingIntelligenceEngine

class RecommendationEngine:
    @staticmethod
    def get_recommendations(campaign_id):
        return MarketingIntelligenceEngine.get_personalized_recommendations(campaign_id)
