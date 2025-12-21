# init_demo_data.py
"""快速初始化演示数据"""

from src.models.species import SpeciesModel
from src.models.relationship import RelationshipModel
from src.models.habitat import HabitatModel
from src.models.observation import ObservationModel


def init_demo_data():
    """初始化演示数据"""
    
    # 初始化模型
    species_model = SpeciesModel()
    relationship_model = RelationshipModel()
    habitat_model = HabitatModel()
    observation_model = ObservationModel()
    
    print("🌱 开始初始化演示数据...")
    
    # 添加物种（至少5个，包含不同类别）
    print("📝 添加物种...")
    tiger = species_model.add_species("东北虎", "哺乳动物", "肉食", "温带森林", protection_level="国家一级")
    deer = species_model.add_species("梅花鹿", "哺乳动物", "草食", "森林草原")
    rabbit = species_model.add_species("野兔", "哺乳动物", "草食", "草原")
    eagle = species_model.add_species("金雕", "鸟类", "肉食", "山地")
    grass = species_model.add_species("草", "植物", "自养", "草原")
    print(f"  ✅ 已添加物种: 东北虎({tiger}), 梅花鹿({deer}), 野兔({rabbit}), 金雕({eagle}), 草({grass})")
    
    # 创建栖息地（2-3个）
    print("🌍 创建栖息地...")
    habitat1 = habitat_model.add_habitat(
        "长白山自然保护区",
        {"latitude": 42.0, "longitude": 128.0},
        "温带森林",
        "国家级"
    )
    habitat2 = habitat_model.add_habitat(
        "内蒙古草原",
        {"latitude": 43.0, "longitude": 116.0},
        "温带草原",
        "省级"
    )
    print(f"  ✅ 已创建栖息地: 长白山自然保护区({habitat1}), 内蒙古草原({habitat2})")
    
    # 关联物种到栖息地
    print("🔗 关联物种到栖息地...")
    habitat_model.link_species(habitat1, tiger)
    habitat_model.link_species(habitat1, deer)
    habitat_model.link_species(habitat2, rabbit)
    habitat_model.link_species(habitat2, grass)
    print("  ✅ 已关联物种到栖息地")
    
    # 建立生态关系（至少5个）
    print("🌐 建立生态关系...")
    relationship_model.create_relationship(tiger, deer, "PREYS_ON")
    relationship_model.create_relationship(deer, grass, "PREYS_ON")
    relationship_model.create_relationship(eagle, rabbit, "PREYS_ON")
    relationship_model.create_relationship(rabbit, grass, "PREYS_ON")
    relationship_model.create_relationship(tiger, rabbit, "PREYS_ON")
    print("  ✅ 已建立5个生态关系")
    
    # 添加观测记录（5-10条）
    print("📊 添加观测记录...")
    for i in range(5):
        observation_model.add_observation(
            tiger, 
            f"研究员{i+1}", 
            "长白山保护区", 
            2, 
            "狩猎"
        )
    
    # 添加更多观测记录
    observation_model.add_observation(deer, "观察员A", "长白山保护区", 5, "觅食")
    observation_model.add_observation(rabbit, "观察员B", "内蒙古草原", 10, "活动")
    observation_model.add_observation(eagle, "观察员C", "长白山保护区", 1, "飞行")
    observation_model.add_observation(grass, "生态学家", "内蒙古草原", 100, "生长")
    
    print("  ✅ 已添加9条观测记录")
    
    print("✅ 演示数据初始化完成！")
    print(f"\n📊 数据统计:")
    print(f"  - 物种数量: {species_model.count_species()}")
    print(f"  - 栖息地数量: {habitat_model.count_habitats()}")
    print(f"  - 生态关系数量: {relationship_model.count_relationships()}")
    print(f"  - 观测记录数量: {observation_model.count_observations()}")


if __name__ == "__main__":
    try:
        init_demo_data()
    except Exception as e:
        print(f"❌ 初始化失败: {e}")
        import traceback
        traceback.print_exc()

