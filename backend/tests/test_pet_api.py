import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.api.pet import PetStateUpdate, read_pet_state, save_pet_state
from app.storage.database import Base
from app.storage.models import PetState, User


class PetStateApiTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
        )
        Base.metadata.create_all(bind=self.engine)
        self.session_factory = sessionmaker(bind=self.engine, autoflush=False, autocommit=False)
        self.db: Session = self.session_factory()
        self.user = User(username="pet-user", password_hash="hash", is_active=True)
        self.db.add(self.user)
        self.db.commit()
        self.db.refresh(self.user)

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def test_read_pet_state_defaults_to_awake(self):
        response = read_pet_state(db=self.db, current_user=self.user)

        self.assertFalse(response.sleeping)
        self.assertEqual(response.stats.energy, 78)
        self.assertEqual(response.position.bottom, 96.0)

    def test_save_pet_state_persists_sleeping_flag(self):
        payload = PetStateUpdate(
            sleeping=True,
            position={"bottom": 140, "left": 42},
            stats={"energy": 17, "hunger": 66, "mood": 71, "thirst": 59},
        )

        response = save_pet_state(payload=payload, db=self.db, current_user=self.user)
        state = self.db.query(PetState).filter(PetState.user_id == self.user.id).one()

        self.assertTrue(response.sleeping)
        self.assertTrue(state.sleeping)
        self.assertEqual(state.energy, 17)
        self.assertEqual(state.position_bottom, 140)
        self.assertEqual(state.position_left, 42)


if __name__ == "__main__":
    unittest.main()
