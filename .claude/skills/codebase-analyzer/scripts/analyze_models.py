#!/usr/bin/env python3
"""
Database Model Analyzer
Extracts database models, schemas, and entity definitions across multiple
ORMs and languages: SQLAlchemy, Django, Prisma, TypeORM, Entity Framework,
GORM, Diesel, and raw SQL schemas.
"""

import json
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional


DETECTED = "detected"
INFERRED = "inferred"


# ========== Python ORM Detection ==========

def extract_sqlalchemy_models(source: str) -> List[Dict]:
    """Extract SQLAlchemy model definitions."""
    models = []

    # SQLAlchemy declarative models: class User(Base): or class User(db.Model):
    model_pattern = r'class\s+(\w+)\s*\(\s*(?:Base|db\.Model|DeclarativeBase|.*Model.*)\s*\)\s*:'

    for match in re.finditer(model_pattern, source):
        model_name = match.group(1)
        model_start = match.end()

        # Find the model body (rough extraction)
        # Look for the next class or end of indent
        remaining = source[model_start:model_start + 2000]

        fields = []
        relationships = []

        # Column definitions: name = Column(Type, ...)
        for col in re.finditer(r'(\w+)\s*=\s*(?:mapped_column|Column)\s*\(\s*(\w+)', remaining):
            fields.append({
                'name': col.group(1),
                'type': col.group(2),
            })

        # Mapped column with Mapped type hint: name: Mapped[str] = mapped_column()
        for col in re.finditer(r'(\w+)\s*:\s*Mapped\[([^\]]+)\]', remaining):
            fields.append({
                'name': col.group(1),
                'type': col.group(2),
            })

        # Relationships: items = relationship("Item", ...)
        for rel in re.finditer(r'(\w+)\s*=\s*relationship\s*\(\s*["\'](\w+)["\']', remaining):
            relationships.append({
                'name': rel.group(1),
                'target': rel.group(2),
            })

        # Table name: __tablename__ = 'users'
        table_match = re.search(r'__tablename__\s*=\s*["\'](\w+)["\']', remaining)
        table_name = table_match.group(1) if table_match else model_name.lower() + 's'

        models.append({
            'name': model_name,
            'table': table_name,
            'orm': 'sqlalchemy',
            'fields': fields,
            'relationships': relationships,
            'confidence': DETECTED,
            'line': source[:match.start()].count('\n') + 1,
        })

    return models


def extract_django_models(source: str) -> List[Dict]:
    """Extract Django model definitions."""
    models = []

    # Django models: class User(models.Model):
    model_pattern = r'class\s+(\w+)\s*\(\s*(?:models\.Model|AbstractUser|AbstractBaseUser)\s*\)\s*:'

    for match in re.finditer(model_pattern, source):
        model_name = match.group(1)
        model_start = match.end()
        remaining = source[model_start:model_start + 2000]

        fields = []
        relationships = []

        # Field definitions: name = models.CharField(...)
        for col in re.finditer(r'(\w+)\s*=\s*models\.(\w+Field)', remaining):
            field_type = col.group(2)
            fields.append({
                'name': col.group(1),
                'type': field_type,
            })

            # ForeignKey, OneToOneField, ManyToManyField are relationships
            if field_type in ('ForeignKey', 'OneToOneField', 'ManyToManyField'):
                # Try to extract target model
                target_match = re.search(rf'{col.group(1)}\s*=\s*models\.{field_type}\s*\(\s*["\']?(\w+)["\']?', remaining)
                if target_match:
                    relationships.append({
                        'name': col.group(1),
                        'target': target_match.group(1),
                        'type': field_type,
                    })

        # Meta class for table name
        meta_match = re.search(r'class\s+Meta\s*:.*?db_table\s*=\s*["\'](\w+)["\']', remaining, re.DOTALL)
        table_name = meta_match.group(1) if meta_match else model_name.lower()

        models.append({
            'name': model_name,
            'table': table_name,
            'orm': 'django',
            'fields': fields,
            'relationships': relationships,
            'confidence': DETECTED,
            'line': source[:match.start()].count('\n') + 1,
        })

    return models


# ========== JavaScript/TypeScript ORM Detection ==========

def extract_prisma_models(source: str) -> List[Dict]:
    """Extract Prisma schema models from .prisma files."""
    models = []

    # model User { ... }
    model_pattern = r'model\s+(\w+)\s*\{([^}]+)\}'

    for match in re.finditer(model_pattern, source, re.DOTALL):
        model_name = match.group(1)
        body = match.group(2)

        fields = []
        relationships = []

        for line in body.strip().split('\n'):
            line = line.strip()
            if not line or line.startswith('//') or line.startswith('@@'):
                continue

            # Field: name Type modifiers
            field_match = re.match(r'(\w+)\s+(\w+)(\[\])?\s*(\?)?', line)
            if field_match:
                field_name = field_match.group(1)
                field_type = field_match.group(2)
                is_array = bool(field_match.group(3))
                is_optional = bool(field_match.group(4))

                fields.append({
                    'name': field_name,
                    'type': field_type,
                    'array': is_array,
                    'optional': is_optional,
                })

                # Check if it's a relation (PascalCase type that's not a primitive)
                primitives = {'String', 'Int', 'Float', 'Boolean', 'DateTime', 'Json', 'Bytes', 'Decimal', 'BigInt'}
                if field_type not in primitives and field_type[0].isupper():
                    relationships.append({
                        'name': field_name,
                        'target': field_type,
                        'array': is_array,
                    })

        models.append({
            'name': model_name,
            'table': model_name,  # Prisma uses model name as table
            'orm': 'prisma',
            'fields': fields,
            'relationships': relationships,
            'confidence': DETECTED,
            'line': source[:match.start()].count('\n') + 1,
        })

    return models


def extract_typeorm_models(source: str) -> List[Dict]:
    """Extract TypeORM entity definitions."""
    models = []

    # @Entity() class User { ... }
    entity_pattern = r'@Entity\s*\(\s*(?:["\'](\w+)["\'])?\s*\)\s*(?:export\s+)?class\s+(\w+)'

    for match in re.finditer(entity_pattern, source):
        table_name = match.group(1) or match.group(2).lower()
        model_name = match.group(2)
        model_start = match.end()
        remaining = source[model_start:model_start + 2000]

        fields = []
        relationships = []

        # @Column() decorator
        for col in re.finditer(r'@Column\s*\([^)]*\)\s*(?:\w+\s*:\s*)?(\w+)\s*(?::\s*(\w+))?', remaining):
            fields.append({
                'name': col.group(1),
                'type': col.group(2) or 'unknown',
            })

        # @PrimaryGeneratedColumn()
        for col in re.finditer(r'@PrimaryGeneratedColumn\s*\([^)]*\)\s*(\w+)', remaining):
            fields.append({
                'name': col.group(1),
                'type': 'id',
                'primary': True,
            })

        # Relationships
        for rel_type in ['OneToOne', 'OneToMany', 'ManyToOne', 'ManyToMany']:
            for rel in re.finditer(rf'@{rel_type}\s*\(\s*\(\)\s*=>\s*(\w+)', remaining):
                relationships.append({
                    'name': rel.group(1).lower(),
                    'target': rel.group(1),
                    'type': rel_type,
                })

        models.append({
            'name': model_name,
            'table': table_name,
            'orm': 'typeorm',
            'fields': fields,
            'relationships': relationships,
            'confidence': DETECTED,
            'line': source[:match.start()].count('\n') + 1,
        })

    return models


def extract_sequelize_models(source: str) -> List[Dict]:
    """Extract Sequelize model definitions."""
    models = []

    # sequelize.define('User', { ... }) or Model.init({ ... })
    define_pattern = r'(?:sequelize\.define|\.init)\s*\(\s*["\'](\w+)["\']'

    for match in re.finditer(define_pattern, source):
        model_name = match.group(1)
        models.append({
            'name': model_name,
            'table': model_name.lower() + 's',
            'orm': 'sequelize',
            'fields': [],  # Would need more complex parsing
            'relationships': [],
            'confidence': INFERRED,
            'line': source[:match.start()].count('\n') + 1,
        })

    return models


# ========== C# Entity Framework Detection ==========

def extract_ef_models(source: str) -> List[Dict]:
    """Extract Entity Framework model definitions."""
    models = []

    # Look for classes with [Table] attribute or DbSet<T> properties
    # [Table("Users")] public class User { ... }
    table_pattern = r'\[Table\s*\(\s*["\'](\w+)["\']\s*\)\]\s*public\s+class\s+(\w+)'

    for match in re.finditer(table_pattern, source):
        table_name = match.group(1)
        model_name = match.group(2)

        models.append({
            'name': model_name,
            'table': table_name,
            'orm': 'entity-framework',
            'fields': [],
            'relationships': [],
            'confidence': DETECTED,
            'line': source[:match.start()].count('\n') + 1,
        })

    # DbSet<T> in DbContext
    dbset_pattern = r'public\s+(?:virtual\s+)?DbSet<(\w+)>\s+(\w+)'
    for match in re.finditer(dbset_pattern, source):
        entity_name = match.group(1)
        # Check if we already have this model
        if not any(m['name'] == entity_name for m in models):
            models.append({
                'name': entity_name,
                'table': match.group(2),  # DbSet name often matches table
                'orm': 'entity-framework',
                'fields': [],
                'relationships': [],
                'confidence': INFERRED,
                'line': source[:match.start()].count('\n') + 1,
            })

    # Entity classes (public class with navigation properties)
    entity_pattern = r'public\s+class\s+(\w+)(?:\s*:\s*\w+)?\s*\{'
    for match in re.finditer(entity_pattern, source):
        class_name = match.group(1)
        if class_name.endswith('Context') or class_name.endswith('Controller'):
            continue

        class_start = match.end()
        remaining = source[class_start:class_start + 1500]

        # Check if it looks like an entity (has properties with typical EF patterns)
        if re.search(r'public\s+(?:int|long|Guid)\s+(?:Id|\w+Id)\s*\{', remaining):
            if not any(m['name'] == class_name for m in models):
                fields = []
                relationships = []

                # Properties
                for prop in re.finditer(r'public\s+(?:virtual\s+)?(\w+\??)\s+(\w+)\s*\{', remaining):
                    prop_type = prop.group(1)
                    prop_name = prop.group(2)

                    fields.append({
                        'name': prop_name,
                        'type': prop_type,
                    })

                    # Navigation property (collection or reference)
                    if 'ICollection' in prop_type or 'List' in prop_type or 'IEnumerable' in prop_type:
                        type_match = re.search(r'<(\w+)>', prop_type)
                        if type_match:
                            relationships.append({
                                'name': prop_name,
                                'target': type_match.group(1),
                                'type': 'collection',
                            })
                    elif prop_type[0].isupper() and prop_type not in ('String', 'DateTime', 'Guid', 'Int32', 'Int64', 'Boolean', 'Decimal'):
                        relationships.append({
                            'name': prop_name,
                            'target': prop_type.rstrip('?'),
                            'type': 'reference',
                        })

                models.append({
                    'name': class_name,
                    'table': class_name + 's',
                    'orm': 'entity-framework',
                    'fields': fields,
                    'relationships': relationships,
                    'confidence': INFERRED,
                    'line': source[:match.start()].count('\n') + 1,
                })

    return models


# ========== Go ORM Detection ==========

def extract_gorm_models(source: str) -> List[Dict]:
    """Extract GORM model definitions."""
    models = []

    # type User struct { gorm.Model ... }
    struct_pattern = r'type\s+(\w+)\s+struct\s*\{([^}]+)\}'

    for match in re.finditer(struct_pattern, source, re.DOTALL):
        struct_name = match.group(1)
        body = match.group(2)

        # Check if it's a GORM model (has gorm.Model or gorm tags)
        if 'gorm.Model' not in body and '`gorm:' not in body and '`json:' not in body:
            continue

        fields = []
        relationships = []

        for line in body.strip().split('\n'):
            line = line.strip()
            if not line:
                continue

            # Field: Name Type `gorm:"..."` or just Name Type
            field_match = re.match(r'(\w+)\s+(\S+)(?:\s+`([^`]+)`)?', line)
            if field_match:
                field_name = field_match.group(1)
                field_type = field_match.group(2)
                tags = field_match.group(3) or ''

                if field_name == 'gorm' and field_type == 'Model':
                    continue  # Skip embedded gorm.Model

                fields.append({
                    'name': field_name,
                    'type': field_type,
                    'tags': tags,
                })

                # Detect relationships (slice or pointer to struct)
                if field_type.startswith('[]') or field_type.startswith('*'):
                    target = field_type.lstrip('[]').lstrip('*')
                    if target[0].isupper():
                        relationships.append({
                            'name': field_name,
                            'target': target,
                        })

        # Table name from TableName() method or snake_case
        table_match = re.search(rf'func\s*\(\s*\w*\s*\*?{struct_name}\s*\)\s*TableName\s*\(\s*\)\s*string\s*\{{\s*return\s*["`](\w+)["`]', source)
        table_name = table_match.group(1) if table_match else struct_name.lower() + 's'

        models.append({
            'name': struct_name,
            'table': table_name,
            'orm': 'gorm',
            'fields': fields,
            'relationships': relationships,
            'confidence': DETECTED,
            'line': source[:match.start()].count('\n') + 1,
        })

    return models


# ========== Rust ORM Detection ==========

def extract_diesel_models(source: str) -> List[Dict]:
    """Extract Diesel model definitions."""
    models = []

    # #[derive(Queryable)] struct User { ... }
    # #[diesel(table_name = users)]
    derive_pattern = r'#\[derive\([^)]*(?:Queryable|Insertable|Identifiable)[^)]*\)\]\s*(?:#\[diesel\(table_name\s*=\s*(\w+)\)\]\s*)?(?:pub\s+)?struct\s+(\w+)'

    for match in re.finditer(derive_pattern, source, re.DOTALL):
        table_name = match.group(1)
        model_name = match.group(2)

        models.append({
            'name': model_name,
            'table': table_name or model_name.lower() + 's',
            'orm': 'diesel',
            'fields': [],
            'relationships': [],
            'confidence': DETECTED,
            'line': source[:match.start()].count('\n') + 1,
        })

    # table! macro
    table_pattern = r'table!\s*\{\s*(\w+)\s*\('
    for match in re.finditer(table_pattern, source):
        table_name = match.group(1)
        if not any(m['table'] == table_name for m in models):
            models.append({
                'name': table_name.title(),
                'table': table_name,
                'orm': 'diesel',
                'fields': [],
                'relationships': [],
                'confidence': INFERRED,
                'line': source[:match.start()].count('\n') + 1,
            })

    return models


# ========== Raw SQL Schema Detection ==========

def extract_sql_schema(source: str) -> List[Dict]:
    """Extract table definitions from SQL files."""
    models = []

    # CREATE TABLE users ( ... )
    create_pattern = r'CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?["`]?(\w+)["`]?\s*\(([^;]+)\)'

    for match in re.finditer(create_pattern, source, re.IGNORECASE | re.DOTALL):
        table_name = match.group(1)
        body = match.group(2)

        fields = []
        relationships = []

        for line in body.split(','):
            line = line.strip()
            if not line:
                continue

            # Skip constraints
            if any(kw in line.upper() for kw in ['PRIMARY KEY', 'FOREIGN KEY', 'UNIQUE', 'CHECK', 'INDEX', 'CONSTRAINT']):
                # Extract foreign key info
                fk_match = re.search(r'FOREIGN\s+KEY\s*\(\s*["`]?(\w+)["`]?\s*\)\s*REFERENCES\s+["`]?(\w+)["`]?', line, re.IGNORECASE)
                if fk_match:
                    relationships.append({
                        'name': fk_match.group(1),
                        'target': fk_match.group(2),
                        'type': 'foreign_key',
                    })
                continue

            # Column definition: name TYPE [constraints]
            col_match = re.match(r'["`]?(\w+)["`]?\s+(\w+(?:\([^)]+\))?)', line)
            if col_match:
                fields.append({
                    'name': col_match.group(1),
                    'type': col_match.group(2),
                })

        models.append({
            'name': table_name.title().replace('_', ''),
            'table': table_name,
            'orm': 'sql',
            'fields': fields,
            'relationships': relationships,
            'confidence': DETECTED,
            'line': source[:match.start()].count('\n') + 1,
        })

    return models


# ========== Main Analysis ==========

def analyze_models(project_path: str) -> Dict:
    """Analyze project for database models."""
    root = Path(project_path).resolve()

    result = {
        'root': str(root),
        'models': [],
        'orms_detected': [],
        'summary': {
            'total_models': 0,
            'by_orm': defaultdict(int),
            'total_fields': 0,
            'total_relationships': 0,
        },
    }

    skip_dirs = {'node_modules', '.venv', 'venv', '__pycache__', 'dist', 'build', '.git', 'vendor', 'target', 'migrations'}

    # Scan for model files
    for filepath in root.rglob('*'):
        if any(skip in filepath.parts for skip in skip_dirs):
            continue
        if not filepath.is_file():
            continue

        suffix = filepath.suffix.lower()
        filename = filepath.name.lower()

        try:
            if suffix in ('.py', '.js', '.ts', '.cs', '.go', '.rs', '.sql', '.prisma'):
                source = filepath.read_text(encoding='utf-8', errors='replace')
            else:
                continue
        except:
            continue

        rel_path = str(filepath.relative_to(root))
        models = []

        # Extract models by language/ORM
        if suffix == '.py':
            models.extend(extract_sqlalchemy_models(source))
            models.extend(extract_django_models(source))

        elif suffix in ('.js', '.ts'):
            models.extend(extract_typeorm_models(source))
            models.extend(extract_sequelize_models(source))

        elif suffix == '.prisma':
            models.extend(extract_prisma_models(source))

        elif suffix == '.cs':
            models.extend(extract_ef_models(source))

        elif suffix == '.go':
            models.extend(extract_gorm_models(source))

        elif suffix == '.rs':
            models.extend(extract_diesel_models(source))

        elif suffix == '.sql':
            models.extend(extract_sql_schema(source))

        # Add file reference
        for model in models:
            model['file'] = rel_path
            result['models'].append(model)

    # Summary
    result['summary']['total_models'] = len(result['models'])
    for model in result['models']:
        result['summary']['by_orm'][model['orm']] += 1
        result['summary']['total_fields'] += len(model.get('fields', []))
        result['summary']['total_relationships'] += len(model.get('relationships', []))

    result['summary']['by_orm'] = dict(result['summary']['by_orm'])
    result['orms_detected'] = list(result['summary']['by_orm'].keys())

    return result


def main():
    if len(sys.argv) < 2:
        print("Usage: analyze_models.py <project_path> [--output file.json]", file=sys.stderr)
        sys.exit(1)

    project_path = sys.argv[1]
    output_file = None

    if '--output' in sys.argv:
        output_file = sys.argv[sys.argv.index('--output') + 1]

    result = analyze_models(project_path)

    # Print summary
    print(f"🗄️  Model Analysis for {Path(project_path).name}")
    print(f"   Models: {result['summary']['total_models']}")
    print(f"   Fields: {result['summary']['total_fields']}")
    print(f"   Relationships: {result['summary']['total_relationships']}")

    if result['orms_detected']:
        print(f"   ORMs: {', '.join(result['orms_detected'])}")

    if result['models']:
        print("\n   Models found:")
        for model in result['models'][:10]:
            print(f"     • {model['name']} ({model['orm']}) - {len(model.get('fields', []))} fields")
        if len(result['models']) > 10:
            print(f"     ... and {len(result['models']) - 10} more")

    if output_file:
        with open(output_file, 'w') as f:
            json.dump(result, f, indent=2)
        print(f"\n💾 Saved to {output_file}")
    else:
        print()
        print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
