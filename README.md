# rstore-platform
All Saleor services started from a single repository

*Keep in mind this repository is for local development only and is not meant to be deployed on any production environment! If you're a RStore developer and just want to try out RStore in your local machine then follow below -

## Requirements
1. [Docker](https://docs.docker.com/install/)
2. [Docker Compose](https://docs.docker.com/compose/install/)


## How to run it?

1. Clone the local repository:

```
$ git clone --single-branch --branch local git@ssh.dev.azure.com:v3/robi-rstore/RStore/rstore-platform --recursive --jobs 3
```

2. Go to the cloned directory:
```
$ cd rstore-platform
$ mv common.env.example common.env
```

3. Put respective configuration files (Look for assistance from your peers):
```
build/* > rstore-dashboard/build/dashboard/
.env > rstore-core/
```
4. Build the application:
```
$ docker-compose build
```

5. If you need to reset your database (due to conflict or other related issues), run the following command. Otherwise continue to step 6:
```
$ docker-compose run --rm api python3 manage.py resetdb
```

6. Apply Django migrations:
```
$ docker-compose run --rm api python3 manage.py migrate
```

7. Collect static files:
```
$ docker-compose run --rm api python3 manage.py collectstatic --noinput
```

8. Store static data (e.g districts, thanas) using following command:
```
$ docker-compose run --rm api python3 manage.py storedb
```

9. Populate the database with example data and create the admin user and different group users:
```
$ docker-compose run --rm api python3 manage.py populatedb --createsuperuser --createmanagers --importmanagers
```
*Note that `--createsuperuser` argument creates an admin account for `rstore_su@rstore.com.bd` with the password set to `5xv?EQE8`.*

10. Run the application:
```
$ docker-compose up
```
*Both storefront and dashboard are quite big frontend projects and it might take up to few minutes for them to compile depending on your CPU. If nothing shows up on port 3000 or 9000 wait until `Compiled successfully` shows in the console output.*


## How to update the subprojects to the newest versions?
This repository contains newest stable versions.
When new release appear, pull new version of this repository.
In order to update all of them to their newest versions, run:
```
$ git submodule update --remote
```

You can find the latest version of Saleor, storefront and dashboard in their individual repositories:

- https://dev.azure.com/robi-rstore/RStore/_git/rstore-core
- https://dev.azure.com/robi-rstore/RStore/_git/rstore-dashboard
- https://dev.azure.com/robi-rstore/RStore/_git/rstore-storefront

## How to solve issues with lack of available space or build errors after update

Most of the time both issues can be solved by cleaning up space taken by old containers. After that, we build again whole platform. 


1. Make sure docker stack is not running
```
$ docker-compose stop
```

2. Remove existing volumes

**Warning!** Proceeding will remove also your database container! If you need existing data, please remove only services which cause problems! https://docs.docker.com/compose/reference/rm/
```
docker-compose rm
```

3. Build fresh containers 
```
docker-compose build
```

4. Now you can run fresh environment using commands from `How to run it?` section. Done!

### Still no available space

If you are getting issues with lack of available space, consider prunning your docker cache:

**Warning!** This will remove:
  - all stopped containers
  - all networks not used by at least one container
  - all dangling images
  - all dangling build cache 
  
  More info: https://docs.docker.com/engine/reference/commandline/system_prune/
  
<details><summary>I've been warned</summary>
<p>

```
$ docker system prune
```

</p>
</details>

## How to run application parts?
  - `docker-compose up api worker` for backend services only
  - `docker-compose up` for backend and frontend services


## Where is the application running?
- Saleor Core (API) - http://localhost:8000
- Saleor Storefront - http://localhost:3000
- Saleor Dashboard - http://localhost:9000
- Jaeger UI (APM) - http://localhost:16686
- Mailhog (Test email interface) - http://localhost:8025 


If you have any questions or feedback, do not hesitate to contact us via Microsoft Teams:

- https://teams.microsoft.com/l/team/19%3a874c000a715342bcad6d07b376c3d249%40thread.tacv2/conversations?groupId=074943c0-7877-48d6-ac48-aeed9b71902a&tenantId=a8a4d78f-f674-4e92-baef-9082594dd26b


## License

As RStore is using the backbone of https://saleor.io/. Please be align with thier [license](https://github.com/mirumee/saleor-platform/blob/master/LICENSE).

Some situations do call for extra code; so we RStore tech team built a custom e-commerce appliance which is not open source and free anymore. 

Thank you.
