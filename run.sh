docker run -d --name dind_agent_container \
    --privileged -e OPENAI_API_KEY="$OPENAI_API_KEY" \
    -v "$PWD":/workdir \
    -p 8501:8501 \
    simple_dind_cli:latest
docker exec -it dind_agent_container sh -c "streamlit run /app/main.py"
docker stop dind_agent_container
docker rm dind_agent_container
