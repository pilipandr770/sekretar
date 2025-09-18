#!/bin/bash
# Production build script with translation compilation (Linux/macOS)

set -e

TAG=${1:-latest}
NO_BUILD=${2:-false}
PUSH=${3:-false}
REGISTRY=${4:-""}

echo "AI Secretary Production Build"
echo "============================"

# Set image name
IMAGE_NAME="ai-secretary"
if [ -n "$REGISTRY" ]; then
    IMAGE_NAME="$REGISTRY/$IMAGE_NAME"
fi

# Pre-build translation compilation
echo ""
echo "Step 1: Pre-compiling translations..."

# Activate virtual environment if available
if [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
    echo "Virtual environment activated"
fi

# Set Flask app
export FLASK_APP=run.py

# Extract messages
echo "Extracting messages..."
pybabel extract -F babel.cfg -k _l -o messages.pot .

# Update translations
echo "Updating translations..."
for lang in en de uk; do
    pybabel update -i messages.pot -d app/translations -l $lang
done

# Compile translations
echo "Compiling translations..."
for lang in en de uk; do
    pybabel compile -d app/translations -l $lang
done

# Verify translation files
TRANSLATION_READY=true
for lang in en de uk; do
    MO_FILE="app/translations/$lang/LC_MESSAGES/messages.mo"
    if [ ! -f "$MO_FILE" ]; then
        echo "Missing compiled translation: $MO_FILE"
        TRANSLATION_READY=false
    else
        SIZE=$(stat -c%s "$MO_FILE" 2>/dev/null || stat -f%z "$MO_FILE")
        echo "✓ $lang translation ready ($SIZE bytes)"
    fi
done

if [ "$TRANSLATION_READY" = false ]; then
    echo "Translation files are not ready for production build!"
    exit 1
fi

if [ "$NO_BUILD" != "true" ]; then
    # Build Docker image
    echo ""
    echo "Step 2: Building Docker image..."
    echo "Image: $IMAGE_NAME:$TAG"
    
    docker build -f Dockerfile.prod -t "$IMAGE_NAME:$TAG" .
    
    echo "Docker image built successfully!"
    
    # Show image info
    echo ""
    echo "Image Information:"
    docker images "$IMAGE_NAME:$TAG" --format "table {{.Repository}}\t{{.Tag}}\t{{.Size}}\t{{.CreatedAt}}"
fi

if [ "$PUSH" = "true" ] && [ "$NO_BUILD" != "true" ]; then
    echo ""
    echo "Step 3: Pushing to registry..."
    
    if [ -z "$REGISTRY" ]; then
        echo "Registry not specified. Use fourth parameter."
        exit 1
    fi
    
    docker push "$IMAGE_NAME:$TAG"
    echo "Image pushed successfully!"
fi

echo ""
echo "Production build completed!"
echo "Image: $IMAGE_NAME:$TAG"

# Show next steps
echo ""
echo "Next Steps:"
echo "1. Test the image: docker run -p 5000:5000 $IMAGE_NAME:$TAG"
echo "2. Deploy with: docker-compose -f docker-compose.prod.yml up -d"
echo "3. Monitor logs: docker-compose -f docker-compose.prod.yml logs -f app"