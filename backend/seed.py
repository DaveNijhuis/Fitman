from sqlalchemy.orm import Session

from models.exercise import Exercise

EXERCISES = [
    # Push A
    {
        "name": "Flat DB Bench Press",
        "muscles": "Chest, Front Delt, Triceps",
        "session": "Push A",
        "position": 0,
        "type": "weight",
        "equip": "Dumbbell",
    },
    {
        "name": "Incline DB Press",
        "muscles": "Upper Chest, Front Delt, Triceps",
        "session": "Push A",
        "position": 1,
        "type": "weight",
        "equip": "Dumbbell",
    },
    {
        "name": "Seated DB Shoulder Press",
        "muscles": "Front Delt, Side Delt, Triceps",
        "session": "Push A",
        "position": 2,
        "type": "weight",
        "equip": "Dumbbell",
    },
    {
        "name": "DB Lateral Raise",
        "muscles": "Side Delt",
        "session": "Push A",
        "position": 3,
        "type": "weight",
        "equip": "Dumbbell",
    },
    {
        "name": "Overhead Triceps Extension",
        "muscles": "Triceps",
        "session": "Push A",
        "position": 4,
        "type": "weight",
        "equip": "Dumbbell",
    },
    {
        "name": "Push-Up",
        "muscles": "Chest, Front Delt, Triceps",
        "session": "Push A",
        "position": 5,
        "type": "bodyweight",
        "equip": "Bodyweight",
    },
    {
        "name": "Chest Dip",
        "muscles": "Chest, Triceps",
        "session": "Push A",
        "position": 6,
        "type": "bodyweight",
        "equip": "Bodyweight",
    },
    # Pull A
    {
        "name": "One-Arm DB Row",
        "muscles": "Lats, Biceps, Rear Delt",
        "session": "Pull A",
        "position": 0,
        "type": "weight",
        "equip": "Dumbbell",
    },
    {
        "name": "Chest-Supported DB Row",
        "muscles": "Lats, Rear Delt, Biceps",
        "session": "Pull A",
        "position": 1,
        "type": "weight",
        "equip": "Dumbbell",
    },
    {
        "name": "DB Pullover",
        "muscles": "Lats, Chest",
        "session": "Pull A",
        "position": 2,
        "type": "weight",
        "equip": "Dumbbell",
    },
    {
        "name": "DB Rear Delt Fly",
        "muscles": "Rear Delt, Traps",
        "session": "Pull A",
        "position": 3,
        "type": "weight",
        "equip": "Dumbbell",
    },
    {
        "name": "Incline DB Curl",
        "muscles": "Biceps",
        "session": "Pull A",
        "position": 4,
        "type": "weight",
        "equip": "Dumbbell",
    },
    {
        "name": "DB Hammer Curl",
        "muscles": "Biceps, Brachialis",
        "session": "Pull A",
        "position": 5,
        "type": "weight",
        "equip": "Dumbbell",
    },
    {
        "name": "Pull-Up",
        "muscles": "Lats, Biceps, Rear Delt",
        "session": "Pull A",
        "position": 6,
        "type": "bodyweight",
        "equip": "Bodyweight",
    },
    # Legs A
    {
        "name": "DB Goblet Squat",
        "muscles": "Quads, Glutes",
        "session": "Legs A",
        "position": 0,
        "type": "weight",
        "equip": "Dumbbell",
    },
    {
        "name": "Bulgarian Split Squat",
        "muscles": "Quads, Glutes",
        "session": "Legs A",
        "position": 1,
        "type": "weight",
        "equip": "Dumbbell",
    },
    {
        "name": "DB Reverse Lunge",
        "muscles": "Quads, Glutes, Hamstrings",
        "session": "Legs A",
        "position": 2,
        "type": "weight",
        "equip": "Dumbbell",
    },
    {
        "name": "Romanian Deadlift",
        "muscles": "Hamstrings, Glutes, Lower Back",
        "session": "Legs A",
        "position": 3,
        "type": "weight",
        "equip": "Dumbbell",
    },
    {
        "name": "Glute Bridge",
        "muscles": "Glutes, Hamstrings",
        "session": "Legs A",
        "position": 4,
        "type": "bodyweight",
        "equip": "Bodyweight",
    },
    {
        "name": "Single-Leg Calf Raise",
        "muscles": "Calves",
        "session": "Legs A",
        "position": 5,
        "type": "bodyweight",
        "equip": "Bodyweight",
    },
]


def seed_exercises(db: Session) -> None:
    if db.query(Exercise).first():
        return
    db.add_all([Exercise(**e) for e in EXERCISES])
    db.commit()
