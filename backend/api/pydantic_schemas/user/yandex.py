from pydantic import BaseModel, field_validator


class Standings(BaseModel):
    contest_id: int
    as_manager: bool
    from_pos: int
    count: int
    show_unofficial: bool

    @field_validator("count")
    @classmethod
    def count_validator(cls, value: int):
        if value < 1:
            raise ValueError("Count must be positive")
        return value


class Submissions(BaseModel):
    contest_id: int
    from_pos: int
    count: int

    @field_validator("from_pos")
    @classmethod
    def from_pos_validator(cls, value: int):
        if value < 1:
            raise ValueError("From position must be positive")
        return value

    @field_validator("count")
    @classmethod
    def count_validator(cls, value: int):
        if value < 1:
            raise ValueError("Count must be positive")
        return value
