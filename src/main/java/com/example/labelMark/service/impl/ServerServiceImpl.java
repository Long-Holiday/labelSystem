package com.example.labelMark.service.impl;

import com.baomidou.mybatisplus.core.conditions.query.QueryWrapper;
import com.example.labelMark.domain.Server;
import com.example.labelMark.domain.SysUser;
import com.example.labelMark.mapper.ServerMapper;
import com.example.labelMark.mapper.SysUserMapper;
import com.example.labelMark.service.GeoServerService;
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
    
    @Resource
    private SysUserMapper sysUserMapper;

    @Override
    public List<Server> getServers(Integer userId) {
        if (userId == null) {
            // 如果没有提供userId，返回空列表
            return List.of();
        }
        
        // 先查询用户信息，确定是否是管理员
        // SysUser user = sysUserMapper.selectById(userId);
        // if (user != null && user.getIsadmin() == 1) {
        //     // 管理员可以查看所有服务
        //     return serverMapper.selectList(null);
        // }
        
        // 非管理员用户只能查看自己创建的服务
        QueryWrapper<Server> wrapper = new QueryWrapper<>();
        wrapper.eq("user_id", userId);
        
        return serverMapper.selectList(wrapper);
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
