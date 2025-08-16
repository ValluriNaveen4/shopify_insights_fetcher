from sqlalchemy import create_engine, Integer, String, Text, JSON, ForeignKey, DateTime
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker
from sqlalchemy.sql import func
from .config import get_settings

settings = get_settings()
engine = create_engine(settings.db_url, echo=False, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)

class Base(DeclarativeBase):
    pass

class Brand(Base):
    __tablename__ = "brands"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    base_url: Mapped[str] = mapped_column(String(512), unique=True, index=True)
    name: Mapped[str | None] = mapped_column(String(256))
    about_text: Mapped[str | None] = mapped_column(Text)
    emails: Mapped[str | None] = mapped_column(Text)  # comma-separated
    phones: Mapped[str | None] = mapped_column(Text)
    socials: Mapped[dict | None] = mapped_column(JSON)
    important_links: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[str] = mapped_column(DateTime(timezone=True), server_default=func.now())

    products: Mapped[list["Product"]] = relationship(back_populates="brand", cascade="all, delete-orphan")
    policies: Mapped[list["Policy"]] = relationship(back_populates="brand", cascade="all, delete-orphan")
    faqs: Mapped[list["FAQ"]] = relationship(back_populates="brand", cascade="all, delete-orphan")

class Product(Base):
    __tablename__ = "products"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    brand_id: Mapped[int] = mapped_column(ForeignKey("brands.id"))
    title: Mapped[str] = mapped_column(String(512))
    handle: Mapped[str | None] = mapped_column(String(512))
    product_type: Mapped[str | None] = mapped_column(String(256))
    vendor: Mapped[str | None] = mapped_column(String(256))
    status: Mapped[str | None] = mapped_column(String(64))
    tags: Mapped[str | None] = mapped_column(Text)
    image: Mapped[str | None] = mapped_column(String(1024))
    url: Mapped[str | None] = mapped_column(String(1024))
    raw: Mapped[dict | None] = mapped_column(JSON)
    is_hero: Mapped[int] = mapped_column(Integer, default=0)

    brand: Mapped["Brand"] = relationship(back_populates="products")

class Policy(Base):
    __tablename__ = "policies"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    brand_id: Mapped[int] = mapped_column(ForeignKey("brands.id"))
    kind: Mapped[str] = mapped_column(String(128))  # privacy, return, refund, shipping, terms
    url: Mapped[str | None] = mapped_column(String(1024))
    content: Mapped[str | None] = mapped_column(Text)

    brand: Mapped["Brand"] = relationship(back_populates="policies")

class FAQ(Base):
    __tablename__ = "faqs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    brand_id: Mapped[int] = mapped_column(ForeignKey("brands.id"))
    question: Mapped[str] = mapped_column(Text)
    answer: Mapped[str | None] = mapped_column(Text)
    url: Mapped[str | None] = mapped_column(String(1024))

    brand: Mapped["Brand"] = relationship(back_populates="faqs")

def init_db():
    Base.metadata.create_all(bind=engine)
