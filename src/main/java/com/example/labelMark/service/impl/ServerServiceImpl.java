package com.example.labelMark.service.impl;

import com.baomidou.mybatisplus.core.conditions.query.QueryWrapper;
import com.example.labelMark.domain.Server;
import com.example.labelMark.mapper.ServerMapper;
import com.example.labelMark.service.ServerService;
import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

import javax.annotation.Resource;
import java.time.LocalDateTime;
import java.util.List;

/**
 * <p>
 *  服务实现类
 * </p>
 *
 * @author hjw
 * @since 2024-04-15
 */
@Service
public class ServerServiceImpl extends ServiceImpl<ServerMapper, Server> implements ServerService {

    @Resource
    private ServerMapper serverMapper;

    @Override
    public List<Server> getServers() {
        return serverMapper.selectList(null);
    }

    @Override
    public int deleteServerByName(String serName) {
        QueryWrapper<Server> queryWrapper = new QueryWrapper<>();
        queryWrapper.eq("ser_name", serName);
        int delete = serverMapper.delete(queryWrapper);
        return delete;
    }

    @Override
    public boolean createServer(Server server) {
        boolean save = save(server);
        return save;
    }


}
